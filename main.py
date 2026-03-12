import random
from datetime import datetime, timedelta
import uvicorn
from fastapi import FastAPI

app = FastAPI()

order_cache: dict = {}

ORDER_STATUSES = [
    "PENDING",
    "ACCEPTED",
    "SHIPPED",
    "IN_TRANSIT",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
    "DELIVERY_FAILED",
]

DELIVERY_FAILED_REASONS = [
    "Customer not available at the delivery address.",
    "Address not found or incomplete.",
    "Access to the delivery location was restricted.",
    "Package refused by the recipient.",
    "Unsafe delivery conditions at the location.",
]

CARRIERS = ["FedEx", "UPS", "DHL", "USPS", "BlueDart"]

TRACKING_EVENTS = [
    "Order placed",
    "Order confirmed",
    "Picked up by carrier",
    "Arrived at sorting facility",
    "Departed sorting facility",
    "Out for delivery",
]

PAYMENT_METHODS = ["Credit Card", "Debit Card", "Digital Wallet", "Bank Transfer"]

BILL_STATUSES = ["PENDING", "PAID", "OVERDUE", "PARTIALLY_PAID"]

REFUND_STATUSES = ["INITIATED", "PROCESSING", "COMPLETED", "FAILED"]

bill_cache: dict = {}
refund_cache: dict = {}


def get_or_create_order(account_id: str, order_id: str) -> dict:
    key = (account_id, order_id)
    if key not in order_cache:
        status = random.choice(ORDER_STATUSES)
        eta = (datetime.now() + timedelta(days=random.randint(1, 7))).strftime("%Y-%m-%d")
        carrier = random.choice(CARRIERS)
        tracking_number = f"{carrier[:2].upper()}{random.randint(100000000, 999999999)}"

        num_events = random.randint(1, len(TRACKING_EVENTS))
        tracking_history = [
            {
                "event": TRACKING_EVENTS[i],
                "timestamp": (datetime.now() - timedelta(hours=(num_events - i) * 6)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }
            for i in range(num_events)
        ]

        order = {
            "account_id": account_id,
            "order_id": order_id,
            "status": status,
            "eta": eta,
            "carrier": carrier,
            "tracking_number": tracking_number,
            "tracking_history": tracking_history,
            "items": [
                {
                    "item_id": f"ITEM-{random.randint(1000, 9999)}",
                    "name": random.choice(["Laptop", "Phone", "Headphones", "Keyboard", "Monitor"]),
                    "quantity": random.randint(1, 3),
                    "price": round(random.uniform(20.0, 1500.0), 2),
                }
                for _ in range(random.randint(1, 4))
            ],
            "shipping_address": "123 Main St, Springfield, US 62701",
        }

        if status == "DELIVERY_FAILED":
            order["failure_reason"] = random.choice(DELIVERY_FAILED_REASONS)

        order_cache[key] = order

    return order_cache[key]


def get_or_create_bill(account_id: str, bill_id: str) -> dict:
    key = (account_id, bill_id)
    if key not in bill_cache:
        status = random.choice(BILL_STATUSES)
        amount = round(random.uniform(50.0, 5000.0), 2)
        paid_amount = round(random.uniform(0, amount), 2) if status == "PARTIALLY_PAID" else (amount if status == "PAID" else 0)
        issue_date = (datetime.now() - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d")
        due_date = (datetime.now() + timedelta(days=random.randint(1, 60))).strftime("%Y-%m-%d")

        num_payments = random.randint(0, 3) if status in ["PAID", "PARTIALLY_PAID"] else 0
        payment_history = [
            {
                "payment_id": f"PAY-{random.randint(100000, 999999)}",
                "amount": round(random.uniform(10.0, amount), 2),
                "method": random.choice(PAYMENT_METHODS),
                "date": (datetime.now() - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d"),
                "status": "SUCCESS",
            }
            for _ in range(num_payments)
        ]

        bill = {
            "account_id": account_id,
            "bill_id": bill_id,
            "status": status,
            "amount": amount,
            "paid_amount": paid_amount,
            "pending_amount": round(amount - paid_amount, 2),
            "issue_date": issue_date,
            "due_date": due_date,
            "description": f"Billing period {issue_date} to {due_date}",
            "payment_history": payment_history,
        }

        bill_cache[key] = bill

    return bill_cache[key]


def get_account_payment_history(account_id: str) -> list:
    """Get all payment history for an account across all bills."""
    all_payments = []
    for (cached_account_id, bill_id), bill in bill_cache.items():
        if cached_account_id == account_id:
            for payment in bill["payment_history"]:
                all_payments.append({
                    "bill_id": bill_id,
                    "amount": amount if (amount := payment.get("amount")) else 0,
                    "method": payment.get("method"),
                    "date": payment.get("date"),
                    "status": payment.get("status"),
                })
    return all_payments


def is_refund_eligible(account_id: str, bill_id: str) -> dict:
    """Check if a bill is eligible for refund."""
    key = (account_id, bill_id)
    if key not in bill_cache:
        return {"eligible": False, "reason": "Bill not found"}

    bill = bill_cache[key]

    if bill["status"] == "PENDING":
        return {"eligible": False, "reason": "Bill is still pending, cannot refund unpaid bills"}

    if bill["status"] == "OVERDUE":
        return {"eligible": False, "reason": "Bill is overdue, contact support for refund eligibility"}

    if bill["paid_amount"] == 0:
        return {"eligible": False, "reason": "No payments made on this bill"}

    # Check if refund was already initiated
    refund_key = (account_id, bill_id)
    if refund_key in refund_cache:
        existing_refund = refund_cache[refund_key]
        if existing_refund["status"] in ["INITIATED", "PROCESSING"]:
            return {"eligible": False, "reason": "Refund already initiated for this bill"}

    return {"eligible": True, "reason": "Bill is eligible for refund"}


def get_or_create_refund(account_id: str, bill_id: str) -> dict | None:
    """Get or create a refund for a bill."""
    key = (account_id, bill_id)

    if key in refund_cache:
        return refund_cache[key]

    # Check eligibility
    eligibility = is_refund_eligible(account_id, bill_id)
    if not eligibility["eligible"]:
        return None

    bill = bill_cache[key]
    refund_status = random.choice(["INITIATED", "PROCESSING"])
    refund_amount = bill["paid_amount"]
    initiated_date = datetime.now().strftime("%Y-%m-%d")
    estimated_completion = (datetime.now() + timedelta(days=random.randint(3, 10))).strftime("%Y-%m-%d")

    refund = {
        "account_id": account_id,
        "bill_id": bill_id,
        "refund_id": f"REF-{random.randint(100000, 999999)}",
        "status": refund_status,
        "refund_amount": refund_amount,
        "initiated_date": initiated_date,
        "estimated_completion": estimated_completion,
        "reason": "Customer requested refund",
    }

    refund_cache[key] = refund

    # Update bill status to reflect refund initiation
    bill["status"] = "REFUND_IN_PROGRESS"

    return refund


@app.get("/accounts/{account_id}/orders/{order_id}", tags=["Orders"])
def get_order_info(account_id: str, order_id: str):
    order = get_or_create_order(account_id, order_id)
    return {
        "account_id": order["account_id"],
        "order_id": order["order_id"],
        "status": order["status"],
        "eta": order["eta"],
        "items": order["items"],
        "shipping_address": order["shipping_address"],
        **({"failure_reason": order["failure_reason"]} if "failure_reason" in order else {}),
    }


@app.get("/accounts/{account_id}/orders/{order_id}/status", tags=["Orders"])
def get_order_status(account_id: str, order_id: str):
    order = get_or_create_order(account_id, order_id)
    response = {
        "account_id": order["account_id"],
        "order_id": order["order_id"],
        "status": order["status"],
        "eta": order["eta"],
    }
    if "failure_reason" in order:
        response["failure_reason"] = order["failure_reason"]
    return response


@app.get("/accounts/{account_id}/orders/{order_id}/tracking", tags=["Orders"])
def get_order_tracking(account_id: str, order_id: str):
    order = get_or_create_order(account_id, order_id)
    return {
        "account_id": order["account_id"],
        "order_id": order["order_id"],
        "status": order["status"],
        "carrier": order["carrier"],
        "tracking_number": order["tracking_number"],
        "eta": order["eta"],
        "tracking_history": order["tracking_history"],
    }


@app.get("/accounts/{account_id}/bills/{bill_id}", tags=["Billing"])
def get_bill_info(account_id: str, bill_id: str):
    bill = get_or_create_bill(account_id, bill_id)
    return {
        "account_id": bill["account_id"],
        "bill_id": bill["bill_id"],
        "status": bill["status"],
        "amount": bill["amount"],
        "paid_amount": bill["paid_amount"],
        "pending_amount": bill["pending_amount"],
        "issue_date": bill["issue_date"],
        "due_date": bill["due_date"],
        "description": bill["description"],
    }


@app.get("/accounts/{account_id}/payment-history", tags=["Billing"])
def get_payment_history(account_id: str):
    # Check if account has any bills
    account_has_bills = any(cached_account_id == account_id for (cached_account_id, _) in bill_cache.keys())

    # Generate sample bills if none exist
    if not account_has_bills:
        for i in range(random.randint(2, 5)):
            bill_id = f"BILL-{random.randint(100000, 999999)}"
            get_or_create_bill(account_id, bill_id)

    payment_history = get_account_payment_history(account_id)
    return {
        "account_id": account_id,
        "total_payments": len(payment_history),
        "payments": payment_history,
    }


@app.get("/accounts/{account_id}/bills/{bill_id}/pdf", tags=["Billing"])
def get_bill_pdf_link(account_id: str, bill_id: str):
    bill = get_or_create_bill(account_id, bill_id)
    pdf_url = f"https://api.example.com/documents/{account_id}/bills/{bill_id}.pdf"
    return {
        "account_id": bill["account_id"],
        "bill_id": bill["bill_id"],
        "pdf_url": pdf_url,
        "status": bill["status"],
        "issue_date": bill["issue_date"],
    }


@app.post("/accounts/{account_id}/bills/{bill_id}/refund/initiate", tags=["Refunds"])
def initiate_refund(account_id: str, bill_id: str):
    eligibility = is_refund_eligible(account_id, bill_id)
    if not eligibility["eligible"]:
        return {
            "success": False,
            "error": eligibility["reason"],
            "account_id": account_id,
            "bill_id": bill_id,
        }

    refund = get_or_create_refund(account_id, bill_id)
    return {
        "success": True,
        "account_id": refund["account_id"],
        "bill_id": refund["bill_id"],
        "refund_id": refund["refund_id"],
        "status": refund["status"],
        "refund_amount": refund["refund_amount"],
        "initiated_date": refund["initiated_date"],
        "estimated_completion": refund["estimated_completion"],
    }


@app.get("/accounts/{account_id}/bills/{bill_id}/refund/eligibility", tags=["Refunds"])
def check_refund_eligibility(account_id: str, bill_id: str):
    eligibility = is_refund_eligible(account_id, bill_id)
    return {
        "account_id": account_id,
        "bill_id": bill_id,
        "eligible": eligibility["eligible"],
        "reason": eligibility["reason"],
    }


@app.get("/accounts/{account_id}/bills/{bill_id}/refund/status", tags=["Refunds"])
def get_refund_status(account_id: str, bill_id: str):
    key = (account_id, bill_id)
    if key not in refund_cache:
        return {
            "account_id": account_id,
            "bill_id": bill_id,
            "status": "NOT_INITIATED",
            "message": "No refund has been initiated for this bill",
        }

    refund = refund_cache[key]
    return {
        "account_id": refund["account_id"],
        "bill_id": refund["bill_id"],
        "refund_id": refund["refund_id"],
        "status": refund["status"],
        "refund_amount": refund["refund_amount"],
        "initiated_date": refund["initiated_date"],
    }


@app.get("/accounts/{account_id}/bills/{bill_id}/refund/estimated-completion", tags=["Refunds"])
def get_refund_estimated_completion(account_id: str, bill_id: str):
    key = (account_id, bill_id)
    if key not in refund_cache:
        return {
            "account_id": account_id,
            "bill_id": bill_id,
            "status": "NOT_INITIATED",
            "message": "No refund has been initiated for this bill",
        }

    refund = refund_cache[key]
    return {
        "account_id": refund["account_id"],
        "bill_id": refund["bill_id"],
        "refund_id": refund["refund_id"],
        "status": refund["status"],
        "estimated_completion": refund["estimated_completion"],
        "initiated_date": refund["initiated_date"],
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
