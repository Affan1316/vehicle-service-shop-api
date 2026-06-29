# Vehicle Service Shop — Unified Entity-Attribute Schema

This is the single-source-of-truth version of the schema: each field's type, key role, and FK
target live in **one row**, in **one table per entity** — no separate "attributes" and
"relationships" sections to fall out of sync. This is what gets translated into SQL `CREATE
TABLE` statements next.

## How the five decisions changed the shape of the model

1. **Record starts at QUOTE** → no lead/inquiry entity. `CUSTOMER` is the first record.
2. **DISPUTE is a full entity** → it gets its own history (opened/resolved, reason, resolution),
   not just a flag on `INVOICE`.
3. **Vehicle can be checked in & diagnosed before a quote/work order exists** → this is the big
   one. It means "vehicle physically at the shop" can't be hung off `WORK_ORDER` or `QUOTE`
   anymore, because neither may exist yet. A new entity, **`VISIT`**, now represents that
   physical presence. `DIAGNOSTIC` attaches to `VISIT`. `QUOTE` *optionally* references the
   `VISIT` it was drafted from (a phone quote with no visit is still allowed). `WORK_ORDER` keeps
   an optional `visit_id` for convenience.
4. **Insurers/fleets get a master record, like VENDOR** → new entity **`PAYER`**, parallel in
   shape to `VENDOR`. `PAYMENT.payer_id` is nullable — null means the customer paid directly.
5. **"Current occupant" is enough for BAY** → no occupancy-history entity. `BAY` just carries a
   pointer to whoever currently holds it.

---

## 1. Front Office

### CUSTOMER
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| customer_id | string | PK | | |
| name | string | | | |
| customer_type | enum(individual, fleet) | | | |
| billing_address | string | | | |
| tax_exempt | boolean | | | |

### VEHICLE
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| vin | string | PK | | |
| customer_id | string | FK | CUSTOMER | |
| make | string | | | |
| model | string | | | |
| year | int | | | |
| current_mileage | int | | | |

### APPOINTMENT — future booking, made ahead of arrival
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| appointment_id | string | PK | | |
| customer_id | string | FK | CUSTOMER | |
| vehicle_id | string | FK | VEHICLE | |
| bay_id | string | FK, nullable | BAY | held tentatively before confirmation |
| requested_date | date | | | |
| confirmed_date | date, nullable | | | |
| status | enum(requested, confirmed, cancelled) | | | |

### VISIT — NEW. The vehicle's physical presence at the shop, independent of quote/work order
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| visit_id | string | PK | | |
| vehicle_id | string | FK | VEHICLE | |
| customer_id | string | FK | CUSTOMER | |
| appointment_id | string | FK, nullable | APPOINTMENT | null = walk-in, no prior booking |
| checked_in_at | datetime | | | |
| checked_out_at | datetime, nullable | | "gets delivered" |
| status | enum(checked_in, in_diagnosis, awaiting_quote, in_service, awaiting_pickup, completed) | | | |

---

## 2. Sales

### QUOTE *(renamed from ESTIMATE)*
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| quote_id | string | PK | | |
| vehicle_id | string | FK | VEHICLE | |
| customer_id | string | FK | CUSTOMER | |
| visit_id | string | FK, nullable | VISIT | set when drafted off a diagnostic; null for a phone/remote quote |
| status | enum(draft, issued, approved, declined, expired) | | | |
| total_amount | decimal | | | the quoted price |
| drafted_at | datetime | | | |
| issued_at | datetime, nullable | | | |
| valid_until | date | | | drives "expires" |
| decline_reason | string, nullable | | | |

### DEPOSIT — NEW
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| deposit_id | string | PK | | |
| quote_id | string | FK | QUOTE | deposit is often collected at approval, before a work order exists |
| work_order_id | string | FK, nullable | WORK_ORDER | filled once the quote becomes a job |
| customer_id | string | FK | CUSTOMER | |
| amount | decimal | | | |
| status | enum(collected, applied, refunded) | | | |
| collected_at | datetime | | | |
| invoice_id | string | FK, nullable | INVOICE | set when applied toward the final invoice |
| refunded_at | datetime, nullable | | | |
| refund_amount | decimal, nullable | | | |

---

## 3. Job Execution

### WORK_ORDER
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| work_order_id | string | PK | | |
| quote_id | string | FK | QUOTE | "the moment a quote turns into a real job" |
| visit_id | string | FK, nullable | VISIT | convenience pointer to originating visit |
| vehicle_id | string | FK | VEHICLE | |
| customer_id | string | FK | CUSTOMER | |
| bay_id | string | FK, nullable | BAY | |
| status | enum(created, scheduled, paused, active, closed, archived) | | | |
| authorized_amount | decimal | | | |
| promised_date | date | | | |
| created_at | datetime | | | |
| scheduled_at | datetime, nullable | | | |
| paused_at | datetime, nullable | | | |
| pause_reason | string, nullable | | | |
| closed_at | datetime, nullable | | | |
| archived_at | datetime, nullable | | | |

### LINE_ITEM
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| line_item_id | string | PK | | |
| work_order_id | string | FK | WORK_ORDER | |
| description | string | | | e.g. "swap the turbo" |
| billing_mode | enum(flat_rate, hourly) | | | |
| price | decimal | | | |
| status | enum(not_started, gated, in_progress, on_hold, completed) | | | |
| hold_reason | string, nullable | | shared by change-order pauses and parts-gating |
| started_at | datetime, nullable | | | |
| completed_at | datetime, nullable | | | |

### CHANGE_ORDER
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| change_order_id | string | PK | | |
| work_order_id | string | FK | WORK_ORDER | |
| line_item_id | string | FK | LINE_ITEM | the one item it pauses |
| finding_id | string | FK, nullable | DIAGNOSTIC_FINDING | set when triggered by a diagnostic |
| reason | string | | | |
| delta_amount | decimal | | | |
| approval_status | enum(issued, approved, declined) | | | |
| approved_by | string, nullable | | | |
| approved_at | datetime, nullable | | | |
| decline_reason | string, nullable | | | |

### DIAGNOSTIC *(now attaches to VISIT, not WORK_ORDER — decision 3)*
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| report_id | string | PK | | |
| visit_id | string | FK | VISIT | can exist before any quote/work order |
| vehicle_id | string | FK | VEHICLE | |
| tech_id | string | FK | TECHNICIAN | |
| performed_at | datetime | | | |
| status | enum(in_progress, completed) | | | |

### DIAGNOSTIC_FINDING — NEW
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| finding_id | string | PK | | |
| report_id | string | FK | DIAGNOSTIC | one report can hold several findings |
| description | string | | | |

### QUALITY_CHECK — NEW
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| qc_id | string | PK | | |
| line_item_id | string | FK | LINE_ITEM | failure sends *this* item back to repair |
| tech_id | string | FK | TECHNICIAN | |
| performed_at | datetime | | | |
| status | enum(passed, failed) | | | |

---

## 4. Shop Resources

### BAY *(decision 5 — current occupant only, no history table)*
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| bay_id | string | PK | | |
| bay_type | string | | | |
| status | enum(available, held, confirmed, occupied, cleaning, maintenance) | | | |
| current_work_order_id | string | FK, nullable | WORK_ORDER | |
| held_until | datetime, nullable | | | |

### TECHNICIAN
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| tech_id | string | PK | | |
| name | string | | | |
| hourly_rate | decimal | | | |

### CERTIFICATION
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| cert_id | string | PK | | |
| tech_id | string | FK | TECHNICIAN | |
| cert_type | string | | | |
| expiry_date | date | | | |

### LABOR_ENTRY — NEW
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| labor_entry_id | string | PK | | |
| tech_id | string | FK | TECHNICIAN | |
| line_item_id | string | FK | LINE_ITEM | multiple techs/sessions per line item |
| work_date | date | | | |
| hours | decimal | | | |

*Certification-blocks-assignment is a validation rule (tech must hold the required cert before a
`LABOR_ENTRY` is allowed), enforced in application logic — not a structural relationship.*

---

## 5. Parts & Procurement

### PART *(catalog — one row per part number)*
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| part_id | string | PK | | |
| part_number | string | | | |
| category | string | | | |
| quantity_on_hand | int | | | |
| is_returnable | boolean | | | |

### PART_INSTANCE — NEW *(one row per physical unit)*
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| part_instance_id | string | PK | | |
| part_id | string | FK | PART | |
| po_line_item_id | string | FK, nullable | PO_LINE_ITEM | null until ordered |
| line_item_id | string | FK, nullable | LINE_ITEM | null until allocated |
| serial_or_lot_number | string, nullable | | | safety-related parts only |
| status | enum(ordered, shipped, received, inspected, rejected, returned, installed) | | | |
| received_at | datetime, nullable | | | |
| inspected_at | datetime, nullable | | | |
| rejection_reason | string, nullable | | | |
| installed_at | datetime, nullable | | | |

### PURCHASE_ORDER
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| po_id | string | PK | | |
| vendor_id | string | FK | VENDOR | |
| status | enum(submitted, confirmed, partially_shipped, complete, cancelled) | | | |
| submitted_at | datetime | | | |
| confirmed_at | datetime, nullable | | | |
| expected_delivery | date | | | |
| cancellation_reason | string, nullable | | | |

### PO_LINE_ITEM — NEW *(needed for "partially shipped" to mean anything)*
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| po_line_item_id | string | PK | | |
| po_id | string | FK | PURCHASE_ORDER | |
| part_id | string | FK | PART | |
| qty_ordered | int | | | |
| qty_shipped | int | | | |
| qty_received | int | | | |

### VENDOR
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| vendor_id | string | PK | | |
| name | string | | | |
| vendor_type | string | | | |

### CREDIT_MEMO — NEW
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| credit_memo_id | string | PK | | |
| core_id | string | FK, nullable | CORE | one of core_id / part_instance_id is set |
| part_instance_id | string | FK, nullable | PART_INSTANCE | for non-core returns |
| vendor_id | string | FK | VENDOR | |
| amount | decimal | | | |
| status | enum(pending, issued) | | | |
| issued_at | datetime, nullable | | | |

### CORE
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| core_id | string | PK | | |
| part_id | string | FK | PART | |
| charge_amount | decimal | | | |
| return_status | enum(charged, shipped, credited) | | | |
| shipped_at | datetime, nullable | | | |

---

## 6. Billing

### INVOICE
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| invoice_id | string | PK | | |
| work_order_id | string | FK | WORK_ORDER | |
| customer_id | string | FK | CUSTOMER | |
| warranty_id | string | FK, nullable | WARRANTY | set when voided/credited under warranty |
| status | enum(issued, disputed, paid, voided, credited) | | | |
| amount_due | decimal | | | |
| issued_at | datetime | | | |
| credit_amount | decimal, nullable | | | |
| credit_reason | string, nullable | | | |

### DISPUTE — NEW, full entity (decision 2)
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| dispute_id | string | PK | | |
| invoice_id | string | FK | INVOICE | |
| opened_by | enum(customer, shop) | | | |
| reason | string | | | |
| status | enum(open, under_review, resolved) | | | |
| opened_at | datetime | | | |
| resolved_at | datetime, nullable | | | |
| resolution | string, nullable | | | |

### PAYMENT
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| payment_id | string | PK | | |
| invoice_id | string | FK | INVOICE | |
| payer_id | string | FK, nullable | PAYER | null = the customer paid directly |
| amount | decimal | | | |
| method | string | | | |
| collected_at | datetime | | | |

### PAYER — NEW (decision 4, modeled like VENDOR)
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| payer_id | string | PK | | |
| name | string | | | |
| payer_type | enum(insurer, warranty_company, fleet_account) | | | |
| contact_info | string | | | |
| billing_terms | string | | | |
| account_number | string | | | |

### STORAGE_CHARGE — NEW
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| storage_charge_id | string | PK | | |
| visit_id | string | FK | VISIT | accrues independent of invoice status |
| daily_rate | decimal | | | |
| start_date | date | | | typically vehicle ready / awaiting_pickup |
| days_accrued | int | | | |

---

## 7. Warranty

### WARRANTY
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| warranty_id | string | PK | | |
| work_order_id | string | FK | WORK_ORDER | |
| coverage_type | string | | | |
| covers_labor | boolean | | | |
| covers_parts | boolean | | | |
| term | string | | | |
| start_date | date | | | set when work order closes |

### WARRANTY_CLAIM — NEW
| Field | Type | Key | References | Notes |
|---|---|---|---|---|
| claim_id | string | PK | | |
| warranty_id | string | FK | WARRANTY | |
| claim_date | date | | | |
| status | enum(filed, approved, denied, resolved) | | | |
| resolution | string, nullable | | | |

---

## Relationships at a glance

| From | To | Cardinality | Note |
|---|---|---|---|
| CUSTOMER | VEHICLE | 1 → many | |
| CUSTOMER | VISIT, QUOTE, WORK_ORDER, INVOICE, DEPOSIT | 1 → many | |
| VEHICLE | VISIT, QUOTE, WORK_ORDER | 1 → many | |
| APPOINTMENT | VISIT | 1 → 0/1 | a visit may have no appointment (walk-in) |
| VISIT | DIAGNOSTIC | 1 → many | |
| VISIT | QUOTE | 1 → 0/many | quote may have no visit (remote quote) |
| VISIT | WORK_ORDER | 1 → 0/many | convenience pointer |
| VISIT | STORAGE_CHARGE | 1 → 0/many | |
| QUOTE | WORK_ORDER | 1 → 0/1 | |
| QUOTE | DEPOSIT | 1 → 0/many | |
| DIAGNOSTIC | DIAGNOSTIC_FINDING | 1 → many | |
| DIAGNOSTIC_FINDING | CHANGE_ORDER | 1 → 0/1 | |
| WORK_ORDER | LINE_ITEM, CHANGE_ORDER | 1 → many | |
| WORK_ORDER | BAY | many → 1 (current) | |
| WORK_ORDER | INVOICE, WARRANTY | 1 → 0/1 | |
| LINE_ITEM | CHANGE_ORDER, LABOR_ENTRY, QUALITY_CHECK, PART_INSTANCE | 1 → many | |
| TECHNICIAN | CERTIFICATION, LABOR_ENTRY, DIAGNOSTIC, QUALITY_CHECK | 1 → many | |
| PART | PART_INSTANCE, CORE | 1 → many | |
| PURCHASE_ORDER | PO_LINE_ITEM | 1 → many | |
| PO_LINE_ITEM | PART_INSTANCE | 1 → many | |
| VENDOR | PURCHASE_ORDER, CREDIT_MEMO | 1 → many | |
| CORE | CREDIT_MEMO | 1 → 0/many | |
| INVOICE | PAYMENT, DISPUTE, DEPOSIT | 1 → many | |
| PAYER | PAYMENT | 1 → many | nullable on PAYMENT |
| WARRANTY | WARRANTY_CLAIM, INVOICE | 1 → many | |

**30 entities total** — 21 from the original model (1 renamed: ESTIMATE → QUOTE) plus 9 new ones
surfaced by the verb-classification pass: `VISIT`, `DEPOSIT`, `PART_INSTANCE`, `PO_LINE_ITEM`,
`CREDIT_MEMO`, `LABOR_ENTRY`, `DIAGNOSTIC_FINDING`, `QUALITY_CHECK`, `DISPUTE`, `PAYER`,
`STORAGE_CHARGE`, `WARRANTY_CLAIM`.
