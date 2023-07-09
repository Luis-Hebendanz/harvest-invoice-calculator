#!/usr/bin/env python3

# This script is currently only used by Jörg, in case someone else is also interested in using it,
# we can make it more flexible.

import argparse
import json
import os
import sys
from datetime import datetime
from fractions import Fraction
from typing import Any, Dict, List, Optional

from sevdesk import Client
from sevdesk.accounting import Invoice, InvoiceStatus, LineItem, Unity

# def find_contacts_by_custom_field_value
#    client: Client,
#    value: str,
#    custom_field_settingid: Union[Unset, None, str] = UNSET,
#    custom_field_settingobject_name: Union[Unset, None, str] = UNSET,
#    custom_field_name: str,
# ) -> Dict[str, Any]:
from sevdesk.client.api.contact import get_contacts
from sevdesk.client.models import DocumentModelTaxType
from sevdesk.common import SevDesk
from sevdesk.contact import Contact


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    api_token = os.environ.get("SEVDESK_API_TOKEN")
    parser.add_argument(
        "--sevdesk-api-token",
        default=api_token,
        required=api_token is None,
        help="Get one from https://my.sevdesk.de/#/admin/userManagement",
    )
    parser.add_argument(
        "--customer",
        required=False,
        type=str,
        help="Ignore customer from json and assume this one instead",
    )
    parser.add_argument(
        "json_file", help="JSON file containing reports (as opposed to stdin)"
    )
    return parser.parse_args()


def get_contact_by_name(client: Client, name: str) -> Contact:
    response = get_contacts.sync_detailed(client=client, name=name)
    SevDesk.raise_for_status(response, f"Failed to find customer with name {name}")
    assert response.parsed is not None
    contacts = response.parsed.objects
    assert isinstance(contacts, list)
    if len(contacts) == 0:
        raise ValueError(
            f"Could not find customer with name {name}. Please create it first in contacts."
        )
    if len(contacts) > 1:
        ids = " ".join(map(lambda c: c.customer_number, contacts))
        raise ValueError(f"Found multiple customers with name: {ids}")
    return Contact._from_contact_model(client, contacts[0])


def item_for_agency(task: Dict[str, Any]) -> LineItem:
    price = float(
        round(
            (Fraction(task["target_cost"]) / Fraction(task["rounded_hours"])),
            2,
        )
    )
    original_price = float(
        round(
            (Fraction(task["source_cost"]) / Fraction(task["rounded_hours"])),
            2,
        )
    )
    text = ""
    if task["source_currency"] != task["target_currency"]:
        text = f"{task['source_currency']} {original_price} x {float(task['exchange_rate'])} = {task['target_currency']} {price}"
    name = f"{task['client']} - {task['task']}"
    return LineItem(
        name=name,
        unity=Unity.HOUR,
        tax=0,
        text=text,
        quantity=task["rounded_hours"],
        price=price,
    )


def item_for_client(task: Dict[str, Any]) -> LineItem:
    text = ""
    price = float(
        round(
            (Fraction(task["source_cost"]) / Fraction(task["rounded_hours"])),
            2,
        )
    )
    return LineItem(
        name=task["task"],
        unity=Unity.HOUR,
        tax=0,
        text=text,
        quantity=task["rounded_hours"],
        price=price,
    )


def create_invoice(
    api_token: str, customer_name: Optional[str], tasks: List[Dict[str, Any]]
) -> None:
    client = Client(base_url="https://my.sevdesk.de/api/v1", token=api_token)

    start = datetime.strptime(str(tasks[0]["start_date"]), "%Y%m%d")
    end = datetime.strptime(str(tasks[0]["end_date"]), "%Y%m%d")
    agency = tasks[0]["agency"]
    has_agency = agency != "-"
    if customer_name:
        billing_target = customer_name
    elif has_agency:
        billing_target = agency
    else:
        billing_target = tasks[0]["client"]
    items = []
    for task in tasks:
        items.append(item_for_agency(task) if has_agency else item_for_client(task))

    customer = get_contact_by_name(client, billing_target)

    head_text = """
    Terms of payment: Payment within 30 days from receipt of invoice without deductions.
    """
    time = start.strftime("%Y-%m")
    invoice = Invoice(
        status=InvoiceStatus.DRAFT,
        header=f"Bill for {time}",
        head_text=head_text,
        customer=customer,
        reference=None,
        tax_type=DocumentModelTaxType.NOTEU,
        delivery_date=start,
        delivery_date_until=end,
        items=items,
    )
    invoice.create(client)
    pass


def main() -> None:
    args = parse_args()
    if args.json_file:
        with open(args.json_file) as f:
            tasks = json.load(f)
    else:
        tasks = json.load(sys.stdin)
    create_invoice(args.sevdesk_api_token, args.customer, tasks)


if __name__ == "__main__":
    main()
