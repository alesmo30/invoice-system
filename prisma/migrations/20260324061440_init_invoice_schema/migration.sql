-- CreateTable
CREATE TABLE "employees" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "first_name" VARCHAR(100) NOT NULL,
    "last_name" VARCHAR(100) NOT NULL,
    "email" VARCHAR(255) NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "employees_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "customers" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "first_name" VARCHAR(100) NOT NULL,
    "last_name" VARCHAR(100) NOT NULL,
    "email" VARCHAR(255),
    "phone" VARCHAR(40),
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "customers_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "products" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "name" VARCHAR(200) NOT NULL,
    "category" VARCHAR(100) NOT NULL,
    "sku" VARCHAR(80) NOT NULL,
    "unit_price" DECIMAL(12,2) NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "products_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "invoices" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "invoice_number" VARCHAR(40) NOT NULL,
    "employee_id" UUID NOT NULL,
    "customer_id" UUID,
    "invoice_date" DATE NOT NULL,
    "total_amount" DECIMAL(14,2) NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "invoices_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "invoice_items" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "invoice_id" UUID NOT NULL,
    "product_id" UUID NOT NULL,
    "quantity" INTEGER NOT NULL,
    "unit_price" DECIMAL(12,2) NOT NULL,
    "line_total" DECIMAL(14,2) NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "invoice_items_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "employees_email_key" ON "employees"("email");

-- CreateIndex
CREATE UNIQUE INDEX "customers_email_key" ON "customers"("email");

-- CreateIndex
CREATE UNIQUE INDEX "products_sku_key" ON "products"("sku");

-- CreateIndex
CREATE UNIQUE INDEX "invoices_invoice_number_key" ON "invoices"("invoice_number");

-- CreateIndex
CREATE INDEX "idx_invoices_employee_id" ON "invoices"("employee_id");

-- CreateIndex
CREATE INDEX "idx_invoices_customer_id" ON "invoices"("customer_id");

-- CreateIndex
CREATE INDEX "idx_invoice_items_invoice_id" ON "invoice_items"("invoice_id");

-- CreateIndex
CREATE INDEX "idx_invoice_items_product_id" ON "invoice_items"("product_id");

-- AddForeignKey
ALTER TABLE "invoices" ADD CONSTRAINT "invoices_employee_id_fkey" FOREIGN KEY ("employee_id") REFERENCES "employees"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "invoices" ADD CONSTRAINT "invoices_customer_id_fkey" FOREIGN KEY ("customer_id") REFERENCES "customers"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "invoice_items" ADD CONSTRAINT "invoice_items_invoice_id_fkey" FOREIGN KEY ("invoice_id") REFERENCES "invoices"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "invoice_items" ADD CONSTRAINT "invoice_items_product_id_fkey" FOREIGN KEY ("product_id") REFERENCES "products"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
