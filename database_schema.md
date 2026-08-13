# Vehicle Service Shop — Complete Database Schema



## Table-by-Table Reference

### SECTION 1 — Independent Core Entities (No Foreign Keys)

---

#### `customer`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **customer_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| name | `VARCHAR(255)` | NO | — | — |
| customer_type | `VARCHAR(20)` | NO | — | CHECK: `individual`, `fleet` |
| tax_exempt | `BOOLEAN` | NO | `false` | — |
| billing_address | `VARCHAR(500)` | YES | — | — |

---

#### `vendor`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **vendor_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| name | `VARCHAR(255)` | NO | — | — |
| vendor_type | `VARCHAR(100)` | YES | — | — |

---

#### `technician`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **tech_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| name | `VARCHAR(255)` | NO | — | — |
| hourly_rate | `NUMERIC(10,2)` | NO | — | CHECK: `>= 0` |

---

#### `part`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **part_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| part_number | `VARCHAR(100)` | NO | — | **UNIQUE** |
| quantity_on_hand | `INTEGER` | NO | `0` | CHECK: `>= 0` |
| is_returnable | `BOOLEAN` | NO | `true` | — |
| category | `VARCHAR(100)` | YES | — | — |
| warranty_required | `BOOLEAN` | NO | `false` | — |

---

#### `payer`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **payer_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| name | `VARCHAR(255)` | NO | — | — |
| payer_type | `VARCHAR(30)` | NO | — | CHECK: `insurer`, `warranty_company`, `fleet_account` |
| contact_info | `VARCHAR(500)` | YES | — | — |
| billing_terms | `VARCHAR(255)` | YES | — | — |
| account_number | `VARCHAR(100)` | YES | — | — |

---

### SECTION 2 — First-Level Dependent Entities

---

#### `vehicle`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **vin** | `VARCHAR(17)` | NO | — | **PK** (natural key) |
| customer_id | `UUID` | NO | — | **FK → customer** (ON DELETE RESTRICT) |
| make | `VARCHAR(100)` | NO | — | — |
| model | `VARCHAR(100)` | NO | — | — |
| year | `INTEGER` | NO | — | CHECK: `1900–2100` |
| current_mileage | `INTEGER` | YES | — | CHECK: `>= 0` |

**Indexes:** `idx_vehicle_customer(customer_id)`

---

#### `certification`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **cert_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| tech_id | `UUID` | NO | — | **FK → technician** (ON DELETE RESTRICT) |
| cert_type | `VARCHAR(100)` | NO | — | — |
| expiry_date | `DATE` | NO | — | — |

**Indexes:** `idx_certification_tech(tech_id)`

---

#### `bay`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **bay_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| status | `VARCHAR(20)` | NO | `'available'` | CHECK: `available`, `held`, `confirmed`, `occupied`, `cleaning`, `maintenance` |
| bay_type | `VARCHAR(100)` | YES | — | — |
| current_work_order_id | `UUID` | YES | — | **FK → work_order** (ON DELETE SET NULL) |
| held_until | `TIMESTAMPTZ` | YES | — | — |

**Indexes:** `idx_bay_current_work_order(current_work_order_id)`

> [!NOTE]
> `bay` ↔ `work_order` has a **circular FK**: `bay.current_work_order_id → work_order` and `work_order.bay_id → bay`. SQLAlchemy resolves this with `post_update=True`.

---

### SECTION 3 — Operations & Front-Office Workflow

---

#### `appointment`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **appointment_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| customer_id | `UUID` | NO | — | **FK → customer** (ON DELETE RESTRICT) |
| vehicle_id | `VARCHAR(17)` | NO | — | **FK → vehicle.vin** (ON DELETE RESTRICT) |
| requested_date | `DATE` | NO | — | App-level: cannot be in the past |
| status | `VARCHAR(20)` | NO | `'requested'` | CHECK: `requested`, `confirmed`, `cancelled`, `checked_in` |
| bay_id | `UUID` | YES | — | **FK → bay** (ON DELETE SET NULL) |
| confirmed_date | `DATE` | YES | — | — |
| preferred_time | `VARCHAR(10)` | YES | — | — |

**Indexes:** `idx_appointment_bay`, `idx_appointment_customer`, `idx_appointment_vehicle`

---

#### `visit`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **visit_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| vehicle_id | `VARCHAR(17)` | NO | — | **FK → vehicle.vin** (ON DELETE RESTRICT) |
| customer_id | `UUID` | NO | — | **FK → customer** (ON DELETE RESTRICT) |
| checked_in_at | `TIMESTAMPTZ` | NO | — | — |
| status | `VARCHAR(20)` | NO | `'checked_in'` | CHECK: `checked_in`, `in_diagnosis`, `awaiting_quote`, `in_service`, `awaiting_pickup`, `completed` |
| appointment_id | `UUID` | YES | — | **FK → appointment** (ON DELETE SET NULL) |
| checked_out_at | `TIMESTAMPTZ` | YES | — | — |
| walk_in | `BOOLEAN` | NO | `false` | — |

**Indexes:** `idx_visit_appointment`, `idx_visit_customer`, `idx_visit_vehicle`

**State Machine (app-level):**
```
checked_in → in_diagnosis | awaiting_quote | in_service
in_diagnosis → awaiting_quote | in_service
awaiting_quote → in_service | completed
in_service → awaiting_pickup
awaiting_pickup → completed
completed → (terminal)
```

**Computed:** `is_active` = `checked_out_at IS NULL`

---

#### `quote`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **quote_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| vehicle_id | `VARCHAR(17)` | NO | — | **FK → vehicle.vin** (ON DELETE RESTRICT) |
| customer_id | `UUID` | NO | — | **FK → customer** (ON DELETE RESTRICT) |
| status | `VARCHAR(20)` | NO | `'draft'` | CHECK: `draft`, `issued`, `approved`, `declined`, `expired` |
| total_amount | `NUMERIC(10,2)` | NO | — | CHECK: `>= 0` |
| drafted_at | `TIMESTAMPTZ` | NO | `now()` | — |
| valid_until | `DATE` | NO | — | — |
| visit_id | `UUID` | YES | — | **FK → visit** (ON DELETE SET NULL) |
| issued_at | `TIMESTAMPTZ` | YES | — | — |
| decline_reason | `VARCHAR(500)` | YES | — | — |

**Indexes:** `idx_quote_customer`, `idx_quote_vehicle`, `idx_quote_visit`

---

#### `work_order`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **work_order_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| quote_id | `UUID` | NO | — | **FK → quote** (ON DELETE RESTRICT), **UNIQUE** |
| vehicle_id | `VARCHAR(17)` | NO | — | **FK → vehicle.vin** (ON DELETE RESTRICT) |
| customer_id | `UUID` | NO | — | **FK → customer** (ON DELETE RESTRICT) |
| status | `VARCHAR(20)` | NO | `'created'` | CHECK: `created`, `scheduled`, `paused`, `active`, `closed`, `archived` |
| authorized_amount | `NUMERIC(10,2)` | NO | — | CHECK: `>= 0` |
| created_at | `TIMESTAMPTZ` | NO | `now()` | — |
| visit_id | `UUID` | YES | — | **FK → visit** (ON DELETE SET NULL) |
| bay_id | `UUID` | YES | — | **FK → bay** (ON DELETE SET NULL) |
| promised_date | `DATE` | YES | — | — |
| scheduled_at | `TIMESTAMPTZ` | YES | — | — |
| paused_at | `TIMESTAMPTZ` | YES | — | — |
| pause_reason | `VARCHAR(500)` | YES | — | — |
| closed_at | `TIMESTAMPTZ` | YES | — | Auto-set when status → `closed` |
| archived_at | `TIMESTAMPTZ` | YES | — | — |
| diagnostic_bypassed | `BOOLEAN` | NO | `false` | — |
| bypass_reason | `VARCHAR(500)` | YES | — | — |

**Indexes:** `idx_work_order_bay`, `idx_work_order_customer`, `idx_work_order_vehicle`, `idx_work_order_visit`

**Computed:** `total_cost` = `SUM(line_item.price)` across child line items

> [!IMPORTANT]
> `quote_id` is **UNIQUE** — each quote can only produce one work order (1:1 relationship).

---

### SECTION 4 — Execution / Line Items

---

#### `line_item`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **line_item_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| work_order_id | `UUID` | NO | — | **FK → work_order** (ON DELETE RESTRICT) |
| description | `VARCHAR(500)` | NO | — | — |
| billing_mode | `VARCHAR(20)` | NO | — | CHECK: `flat_rate`, `hourly` |
| price | `NUMERIC(10,2)` | NO | — | CHECK: `>= 0` |
| status | `VARCHAR(20)` | NO | `'not_started'` | CHECK: `not_started`, `gated`, `in_progress`, `on_hold`, `completed` |
| hold_reason | `VARCHAR(500)` | YES | — | — |
| started_at | `TIMESTAMPTZ` | YES | — | — |
| completed_at | `TIMESTAMPTZ` | YES | — | — |
| is_complimentary | `BOOLEAN` | NO | `false` | — |
| warranty_required | `BOOLEAN` | NO | `false` | — |

**Indexes:** `idx_line_item_work_order(work_order_id)`

---

#### `diagnostic`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **report_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| visit_id | `UUID` | NO | — | **FK → visit** (ON DELETE RESTRICT) |
| vehicle_id | `VARCHAR(17)` | NO | — | **FK → vehicle.vin** (ON DELETE RESTRICT) |
| tech_id | `UUID` | NO | — | **FK → technician** (ON DELETE RESTRICT) |
| performed_at | `TIMESTAMPTZ` | NO | `now()` | — |
| status | `VARCHAR(20)` | NO | `'in_progress'` | CHECK: `in_progress`, `completed` |

**Indexes:** `idx_diagnostic_tech`, `idx_diagnostic_vehicle`, `idx_diagnostic_visit`

---

#### `diagnostic_finding`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **finding_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| report_id | `UUID` | NO | — | **FK → diagnostic** (ON DELETE RESTRICT) |
| description | `VARCHAR(1000)` | NO | — | — |
| recommended_service | `VARCHAR(500)` | YES | — | — |
| is_critical | `BOOLEAN` | NO | `false` | — |

**Indexes:** `idx_diagnostic_finding_report(report_id)`

---

#### `diagnostic_template`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **template_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| name | `VARCHAR(200)` | NO | — | — |
| is_active | `BOOLEAN` | NO | `true` | — |

---

#### `diagnostic_template_item`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **item_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| template_id | `UUID` | NO | — | **FK → diagnostic_template** (ON DELETE CASCADE) |
| description | `VARCHAR(500)` | NO | — | — |

**Indexes:** `idx_diagnostic_template_item_template(template_id)`

---

#### `labor_entry`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **labor_entry_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| tech_id | `UUID` | NO | — | **FK → technician** (ON DELETE RESTRICT) |
| line_item_id | `UUID` | NO | — | **FK → line_item** (ON DELETE RESTRICT) |
| work_date | `DATE` | NO | — | — |
| hours | `NUMERIC(5,2)` | NO | — | CHECK: `> 0` |

**Indexes:** `idx_labor_entry_line_item`, `idx_labor_entry_tech`

---

#### `quality_check`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **qc_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| line_item_id | `UUID` | NO | — | **FK → line_item** (ON DELETE RESTRICT) |
| tech_id | `UUID` | NO | — | **FK → technician** (ON DELETE RESTRICT) |
| performed_at | `TIMESTAMPTZ` | NO | `now()` | — |
| status | `VARCHAR(20)` | NO | — | CHECK: `passed`, `failed` |

**Indexes:** `idx_quality_check_line_item`, `idx_quality_check_tech`

---

#### `change_order`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **change_order_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| work_order_id | `UUID` | NO | — | **FK → work_order** (ON DELETE RESTRICT) |
| line_item_id | `UUID` | NO | — | **FK → line_item** (ON DELETE RESTRICT) |
| reason | `VARCHAR(500)` | NO | — | — |
| delta_amount | `NUMERIC(10,2)` | NO | — | — (can be negative) |
| approval_status | `VARCHAR(20)` | NO | `'issued'` | CHECK: `issued`, `approved`, `declined` |
| finding_id | `UUID` | YES | — | **FK → diagnostic_finding** (ON DELETE SET NULL), **UNIQUE** |
| approved_by | `VARCHAR(255)` | YES | — | — |
| approved_at | `TIMESTAMPTZ` | YES | — | — |
| decline_reason | `VARCHAR(500)` | YES | — | — |

**Indexes:** `idx_change_order_line_item`, `idx_change_order_work_order`

> [!NOTE]
> `finding_id` is **UNIQUE** — each diagnostic finding can trigger at most one change order.

---

### SECTION 5 — Procurement & Inventory

---

#### `purchase_order`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **po_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| vendor_id | `UUID` | NO | — | **FK → vendor** (ON DELETE RESTRICT) |
| status | `VARCHAR(20)` | NO | `'submitted'` | CHECK: `submitted`, `confirmed`, `partially_shipped`, `complete`, `cancelled` |
| submitted_at | `TIMESTAMPTZ` | NO | `now()` | — |
| confirmed_at | `TIMESTAMPTZ` | YES | — | — |
| expected_delivery | `DATE` | YES | — | — |
| cancellation_reason | `VARCHAR(500)` | YES | — | — |

**Indexes:** `idx_purchase_order_vendor(vendor_id)`

---

#### `po_line_item`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **po_line_item_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| po_id | `UUID` | NO | — | **FK → purchase_order** (ON DELETE RESTRICT) |
| part_id | `UUID` | NO | — | **FK → part** (ON DELETE RESTRICT) |
| qty_ordered | `INTEGER` | NO | — | CHECK: `> 0` |
| qty_shipped | `INTEGER` | NO | `0` | CHECK: `>= 0` |
| qty_received | `INTEGER` | NO | `0` | CHECK: `>= 0` |

**Indexes:** `idx_po_line_item_part`, `idx_po_line_item_po`

---

#### `part_instance`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **part_instance_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| part_id | `UUID` | NO | — | **FK → part** (ON DELETE RESTRICT) |
| status | `VARCHAR(20)` | NO | `'ordered'` | CHECK: `ordered`, `shipped`, `received`, `inspected`, `rejected`, `returned`, `installed` |
| po_line_item_id | `UUID` | YES | — | **FK → po_line_item** (ON DELETE SET NULL) |
| line_item_id | `UUID` | YES | — | **FK → line_item** (ON DELETE SET NULL) |
| serial_or_lot_number | `VARCHAR(100)` | YES | — | — |
| received_at | `TIMESTAMPTZ` | YES | — | — |
| inspected_at | `TIMESTAMPTZ` | YES | — | — |
| rejection_reason | `VARCHAR(500)` | YES | — | — |
| installed_at | `TIMESTAMPTZ` | YES | — | — |

**Indexes:** `idx_part_instance_line_item`, `idx_part_instance_part`, `idx_part_instance_po_line_item`

---

#### `core`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **core_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| part_id | `UUID` | NO | — | **FK → part** (ON DELETE RESTRICT) |
| charge_amount | `NUMERIC(10,2)` | NO | — | CHECK: `>= 0` |
| return_status | `VARCHAR(20)` | NO | `'charged'` | CHECK: `charged`, `shipped`, `credited` |
| shipped_at | `TIMESTAMPTZ` | YES | — | — |

**Indexes:** `idx_core_part(part_id)`

---

#### `credit_memo`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **credit_memo_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| vendor_id | `UUID` | NO | — | **FK → vendor** (ON DELETE RESTRICT) |
| amount | `NUMERIC(10,2)` | NO | — | CHECK: `>= 0` |
| status | `VARCHAR(20)` | NO | `'pending'` | CHECK: `pending`, `issued` |
| core_id | `UUID` | YES | — | **FK → core** (ON DELETE RESTRICT) |
| part_instance_id | `UUID` | YES | — | **FK → part_instance** (ON DELETE RESTRICT) |
| issued_at | `TIMESTAMPTZ` | YES | — | — |

**Indexes:** `idx_credit_memo_core`, `idx_credit_memo_part_instance`, `idx_credit_memo_vendor`

> [!IMPORTANT]
> **Exclusive-arc constraint:** Exactly one of `core_id` or `part_instance_id` must be non-null (enforced by `chk_credit_memo_exactly_one_source`).

---

### SECTION 6 — Billing & Financials

---

#### `invoice`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **invoice_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| work_order_id | `UUID` | NO | — | **FK → work_order** (ON DELETE RESTRICT), **UNIQUE** |
| customer_id | `UUID` | NO | — | **FK → customer** (ON DELETE RESTRICT) |
| status | `VARCHAR(20)` | NO | `'issued'` | CHECK: `issued`, `disputed`, `paid`, `voided`, `credited` |
| amount_due | `NUMERIC(10,2)` | NO | — | CHECK: `>= 0` |
| issued_at | `TIMESTAMPTZ` | NO | `now()` | — |
| warranty_id | `UUID` | YES | — | **FK → warranty** (ON DELETE SET NULL) |
| credit_amount | `NUMERIC(10,2)` | YES | — | — |
| credit_reason | `VARCHAR(500)` | YES | — | — |

**Indexes:** `idx_invoice_customer`, `idx_invoice_warranty`

**Computed:** `total_balance` = `amount_due − COALESCE(credit_amount, 0) − SUM(payment.amount)`

> [!IMPORTANT]
> `work_order_id` is **UNIQUE** — each work order produces exactly one invoice (1:1).

---

#### `dispute`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **dispute_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| invoice_id | `UUID` | NO | — | **FK → invoice** (ON DELETE RESTRICT) |
| opened_by | `VARCHAR(20)` | NO | — | CHECK: `customer`, `shop` |
| reason | `VARCHAR(500)` | NO | — | — |
| status | `VARCHAR(20)` | NO | `'open'` | CHECK: `open`, `under_review`, `resolved` |
| opened_at | `TIMESTAMPTZ` | NO | `now()` | — |
| resolved_at | `TIMESTAMPTZ` | YES | — | — |
| resolution | `VARCHAR(1000)` | YES | — | — |

**Indexes:** `idx_dispute_invoice(invoice_id)`

---

#### `payment`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **payment_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| invoice_id | `UUID` | NO | — | **FK → invoice** (ON DELETE RESTRICT) |
| amount | `NUMERIC(10,2)` | NO | — | CHECK: `> 0` |
| method | `VARCHAR(50)` | NO | — | — |
| collected_at | `TIMESTAMPTZ` | NO | `now()` | — |
| payer_id | `UUID` | YES | — | **FK → payer** (ON DELETE SET NULL) |

**Indexes:** `idx_payment_invoice`, `idx_payment_payer`

---

#### `deposit`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **deposit_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| quote_id | `UUID` | NO | — | **FK → quote** (ON DELETE RESTRICT) |
| customer_id | `UUID` | NO | — | **FK → customer** (ON DELETE RESTRICT) |
| amount | `NUMERIC(10,2)` | NO | — | CHECK: `> 0` |
| status | `VARCHAR(20)` | NO | `'collected'` | CHECK: `collected`, `applied`, `refunded` |
| collected_at | `TIMESTAMPTZ` | NO | `now()` | — |
| work_order_id | `UUID` | YES | — | **FK → work_order** (ON DELETE SET NULL) |
| invoice_id | `UUID` | YES | — | **FK → invoice** (ON DELETE SET NULL) |
| refunded_at | `TIMESTAMPTZ` | YES | — | — |
| refund_amount | `NUMERIC(10,2)` | YES | — | — |

**Indexes:** `idx_deposit_customer`, `idx_deposit_invoice`, `idx_deposit_quote`, `idx_deposit_work_order`

---

#### `storage_charge`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **storage_charge_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| visit_id | `UUID` | NO | — | **FK → visit** (ON DELETE RESTRICT) |
| daily_rate | `NUMERIC(10,2)` | NO | — | CHECK: `>= 0` |
| start_date | `DATE` | NO | — | — |
| days_accrued | `INTEGER` | NO | `0` | CHECK: `>= 0` |

**Indexes:** `idx_storage_charge_visit(visit_id)`

**Computed:** `total_charge` = `daily_rate × GREATEST(CURRENT_DATE − start_date, 0)`

---

### SECTION 7 — Warranties

---

#### `warranty`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **warranty_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| work_order_id | `UUID` | NO | — | **FK → work_order** (ON DELETE RESTRICT), **UNIQUE** |
| covers_labor | `BOOLEAN` | NO | `false` | — |
| covers_parts | `BOOLEAN` | NO | `false` | — |
| coverage_type | `VARCHAR(100)` | YES | — | — |
| term | `VARCHAR(100)` | YES | — | — |
| start_date | `DATE` | YES | — | — |

> [!NOTE]
> `work_order_id` is **UNIQUE** — each work order has at most one warranty (1:1).

---

#### `warranty_claim`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **claim_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| warranty_id | `UUID` | NO | — | **FK → warranty** (ON DELETE RESTRICT) |
| claim_date | `DATE` | NO | — | — |
| status | `VARCHAR(20)` | NO | `'filed'` | CHECK: `filed`, `approved`, `denied`, `resolved` |
| resolution | `VARCHAR(1000)` | YES | — | — |

**Indexes:** `idx_warranty_claim_warranty(warranty_id)`

---

### SECTION 8 — Authentication

---

#### `user_account`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| **user_id** | `UUID` | NO | `gen_random_uuid()` | **PK** |
| username | `VARCHAR(100)` | NO | — | **UNIQUE** |
| email | `VARCHAR(255)` | NO | — | **UNIQUE** |
| password_hash | `VARCHAR(255)` | NO | — | — |
| role | `VARCHAR(50)` | NO | `'customer'` | App-level CHECK: `manager`, `advisor`, `technician`, `customer` |
| is_active | `BOOLEAN` | NO | `true` | — |
| customer_id | `UUID` | YES | — | **FK → customer** (ON DELETE SET NULL) |
| tech_id | `UUID` | YES | — | **FK → technician** (ON DELETE SET NULL) |

> [!NOTE]
> This table was **not** part of the original SQL schema — it was added manually for JWT authentication.

---

## Event Listeners (Application-Level Triggers)

These are **not** database triggers — they are SQLAlchemy ORM event listeners defined in [models.py](file:///D:/coding%20projects/auto_shop_backend_2/app/models/models.py#L1206-L1243).

| Event | Trigger | Effect |
|-------|---------|--------|
| `Deposit.work_order` set | A deposit is linked to a work order | Work order `status` → `'scheduled'` |
| `Deposit.work_order_id` set | work_order_id FK set directly | Same as above (identity-map lookup) |
| `WorkOrder.status` → `closed` | Work order closed | `closed_at` auto-set to `now(UTC)` |
| `Visit.checked_out_at` set | Visit is checked out | `status` → `'completed'` |
| `Appointment.status` → `confirmed` | Appointment confirmed | Linked bay `status` → `'confirmed'` |

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Total tables | **31** |
| Independent (no FK) | 5 (`customer`, `vendor`, `technician`, `part`, `payer`) |
| Plus standalone lookup | 1 (`diagnostic_template`) |
| 1:1 relationships | 3 (quote↔work_order, work_order↔invoice, work_order↔warranty) |
| Exclusive-arc constraints | 1 (`credit_memo`: core XOR part_instance) |
| Computed/hybrid properties | 4 (`total_cost`, `total_balance`, `total_charge`, `is_active`) |
| Event listeners | 5 |
