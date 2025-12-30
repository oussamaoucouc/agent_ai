-- CRM Database Schema and Sample Data
-- For MCP PostgreSQL Testing

-- Create schema
CREATE SCHEMA IF NOT EXISTS crm;
SET search_path TO crm;

-- =====================================================
-- TABLE: customers
-- =====================================================
CREATE TABLE IF NOT EXISTS customers (
    customer_id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    company VARCHAR(200),
    address VARCHAR(500),
    city VARCHAR(100),
    country VARCHAR(100),
    postal_code VARCHAR(20),
    customer_type VARCHAR(50) DEFAULT 'standard', -- 'standard', 'premium', 'enterprise'
    credit_limit DECIMAL(12, 2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- =====================================================
-- TABLE: products
-- =====================================================
CREATE TABLE IF NOT EXISTS products (
    product_id SERIAL PRIMARY KEY,
    sku VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    unit_price DECIMAL(12, 2) NOT NULL,
    cost_price DECIMAL(12, 2),
    stock_quantity INTEGER DEFAULT 0,
    min_stock_level INTEGER DEFAULT 10,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- TABLE: invoices
-- =====================================================
CREATE TABLE IF NOT EXISTS invoices (
    invoice_id SERIAL PRIMARY KEY,
    invoice_number VARCHAR(50) UNIQUE NOT NULL,
    customer_id INTEGER REFERENCES customers(customer_id),
    invoice_date DATE NOT NULL,
    due_date DATE NOT NULL,
    subtotal DECIMAL(12, 2) DEFAULT 0.00,
    tax_amount DECIMAL(12, 2) DEFAULT 0.00,
    discount_amount DECIMAL(12, 2) DEFAULT 0.00,
    total_amount DECIMAL(12, 2) DEFAULT 0.00,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'paid', 'overdue', 'cancelled'
    payment_method VARCHAR(50), -- 'cash', 'credit_card', 'bank_transfer', 'check'
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- TABLE: articles (invoice line items)
-- =====================================================
CREATE TABLE IF NOT EXISTS articles (
    article_id SERIAL PRIMARY KEY,
    invoice_id INTEGER REFERENCES invoices(invoice_id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(product_id),
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(12, 2) NOT NULL,
    discount_percent DECIMAL(5, 2) DEFAULT 0.00,
    line_total DECIMAL(12, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- SAMPLE DATA: Customers
-- =====================================================
INSERT INTO customers (first_name, last_name, email, phone, company, address, city, country, postal_code, customer_type, credit_limit) VALUES
('Jean', 'Dupont', 'jean.dupont@example.fr', '+33 1 23 45 67 89', 'Tech Solutions SARL', '15 Rue de la Paix', 'Paris', 'France', '75001', 'premium', 50000.00),
('Marie', 'Martin', 'marie.martin@example.fr', '+33 6 12 34 56 78', 'Digital Agency', '28 Avenue des Champs-Élysées', 'Paris', 'France', '75008', 'enterprise', 100000.00),
('Ahmed', 'Benali', 'ahmed.benali@example.ma', '+212 5 22 33 44 55', 'Maroc Import Export', '45 Boulevard Mohammed V', 'Casablanca', 'Morocco', '20000', 'standard', 15000.00),
('Sophie', 'Laurent', 'sophie.laurent@example.fr', '+33 4 56 78 90 12', 'Provence Trading', '12 Cours Mirabeau', 'Aix-en-Provence', 'France', '13100', 'premium', 35000.00),
('Carlos', 'Rodriguez', 'carlos.rodriguez@example.es', '+34 91 234 5678', 'Barcelona Tech Hub', 'Carrer de Mallorca 401', 'Barcelona', 'Spain', '08013', 'enterprise', 75000.00),
('Emma', 'Wilson', 'emma.wilson@example.uk', '+44 20 7946 0958', 'London Consulting Ltd', '100 Oxford Street', 'London', 'United Kingdom', 'W1D 1LL', 'premium', 60000.00),
('Hans', 'Mueller', 'hans.mueller@example.de', '+49 30 1234567', 'Berlin Innovations GmbH', 'Unter den Linden 77', 'Berlin', 'Germany', '10117', 'enterprise', 120000.00),
('Fatima', 'Zahra', 'fatima.zahra@example.ma', '+212 6 11 22 33 44', 'Rabat Services', '23 Avenue Hassan II', 'Rabat', 'Morocco', '10000', 'standard', 20000.00),
('Pierre', 'Moreau', 'pierre.moreau@example.fr', '+33 3 88 77 66 55', 'Strasbourg Logistics', '5 Place Kléber', 'Strasbourg', 'France', '67000', 'standard', 25000.00),
('Isabella', 'Rossi', 'isabella.rossi@example.it', '+39 02 1234 5678', 'Milano Fashion SRL', 'Via Montenapoleone 8', 'Milan', 'Italy', '20121', 'premium', 80000.00),
('Omar', 'Hassan', 'omar.hassan@example.eg', '+20 2 2345 6789', 'Cairo Trading Co', '15 Tahrir Square', 'Cairo', 'Egypt', '11511', 'standard', 18000.00),
('Lucie', 'Bernard', 'lucie.bernard@example.fr', '+33 5 61 62 63 64', 'Toulouse Aerospace', '8 Allée Jean Jaurès', 'Toulouse', 'France', '31000', 'enterprise', 150000.00);

-- =====================================================
-- SAMPLE DATA: Products
-- =====================================================
INSERT INTO products (sku, name, description, category, unit_price, cost_price, stock_quantity, min_stock_level) VALUES
('LAPTOP-PRO-001', 'ProBook Laptop 15"', 'Professional laptop with 16GB RAM, 512GB SSD, Intel i7', 'Electronics', 1299.99, 950.00, 45, 10),
('LAPTOP-STD-002', 'Standard Laptop 14"', 'Business laptop with 8GB RAM, 256GB SSD, Intel i5', 'Electronics', 799.99, 580.00, 80, 15),
('MONITOR-4K-001', 'UltraView 4K Monitor 27"', '4K UHD professional monitor with USB-C', 'Electronics', 549.99, 380.00, 60, 10),
('KEYBOARD-WL-001', 'Wireless Mechanical Keyboard', 'RGB backlit wireless mechanical keyboard', 'Accessories', 129.99, 65.00, 150, 25),
('MOUSE-WL-001', 'Ergonomic Wireless Mouse', 'Precision wireless mouse with ergonomic design', 'Accessories', 79.99, 35.00, 200, 30),
('HEADSET-PRO-001', 'ProAudio Headset', 'Noise-cancelling professional headset with mic', 'Audio', 199.99, 110.00, 75, 15),
('WEBCAM-HD-001', 'HD Webcam 1080p', 'Full HD webcam with auto-focus and light correction', 'Electronics', 89.99, 45.00, 120, 20),
('DOCK-USB-001', 'USB-C Docking Station', 'Multi-port USB-C dock with dual HDMI', 'Accessories', 249.99, 140.00, 55, 10),
('CHAIR-ERG-001', 'ErgoComfort Office Chair', 'Ergonomic office chair with lumbar support', 'Furniture', 449.99, 280.00, 30, 5),
('DESK-ADJ-001', 'Adjustable Standing Desk', 'Electric height-adjustable desk 160x80cm', 'Furniture', 699.99, 420.00, 20, 3),
('PRINTER-LJ-001', 'LaserJet Pro Printer', 'Color laser printer with duplex and WiFi', 'Electronics', 399.99, 280.00, 25, 5),
('TABLET-PRO-001', 'ProTab 12.9"', 'Professional tablet with stylus support', 'Electronics', 899.99, 650.00, 35, 8),
('CABLE-HDMI-001', 'HDMI Cable 2m', 'High-speed HDMI 2.1 cable', 'Accessories', 24.99, 8.00, 500, 50),
('CABLE-USB-001', 'USB-C Cable 1m', 'Fast charging USB-C cable', 'Accessories', 19.99, 5.00, 600, 75),
('SOFTWARE-OFF-001', 'Office Suite License', 'Annual license for office productivity suite', 'Software', 149.99, 80.00, 999, 100),
('SOFTWARE-SEC-001', 'Security Suite License', 'Annual antivirus and security license', 'Software', 79.99, 40.00, 999, 100),
('BACKUP-HDD-001', 'External HDD 2TB', 'Portable external hard drive 2TB', 'Storage', 89.99, 55.00, 90, 15),
('BACKUP-SSD-001', 'External SSD 1TB', 'Fast portable SSD 1TB', 'Storage', 149.99, 95.00, 65, 10),
('ROUTER-WIFI-001', 'WiFi 6 Router', 'High-performance WiFi 6 mesh router', 'Networking', 299.99, 180.00, 40, 8),
('SWITCH-NET-001', 'Gigabit Switch 8-port', '8-port gigabit ethernet switch', 'Networking', 69.99, 35.00, 100, 15);

-- =====================================================
-- SAMPLE DATA: Invoices
-- =====================================================
INSERT INTO invoices (invoice_number, customer_id, invoice_date, due_date, subtotal, tax_amount, discount_amount, total_amount, status, payment_method, notes) VALUES
('INV-2024-0001', 1, '2024-01-15', '2024-02-15', 2649.97, 529.99, 0.00, 3179.96, 'paid', 'bank_transfer', 'Q1 equipment order'),
('INV-2024-0002', 2, '2024-01-22', '2024-02-22', 5499.93, 1099.99, 274.99, 6324.93, 'paid', 'credit_card', 'Office renovation project'),
('INV-2024-0003', 3, '2024-02-05', '2024-03-05', 1599.98, 319.99, 0.00, 1919.97, 'paid', 'bank_transfer', 'Standard order'),
('INV-2024-0004', 4, '2024-02-18', '2024-03-18', 899.99, 180.00, 45.00, 1034.99, 'paid', 'credit_card', NULL),
('INV-2024-0005', 5, '2024-03-01', '2024-04-01', 8999.90, 1799.98, 449.99, 10349.89, 'paid', 'bank_transfer', 'Large enterprise order'),
('INV-2024-0006', 6, '2024-03-15', '2024-04-15', 3249.96, 649.99, 0.00, 3899.95, 'paid', 'bank_transfer', NULL),
('INV-2024-0007', 7, '2024-04-02', '2024-05-02', 12599.88, 2519.98, 629.99, 14489.87, 'paid', 'bank_transfer', 'Annual equipment refresh'),
('INV-2024-0008', 1, '2024-04-20', '2024-05-20', 749.97, 149.99, 0.00, 899.96, 'paid', 'credit_card', 'Additional accessories'),
('INV-2024-0009', 8, '2024-05-10', '2024-06-10', 1849.97, 370.00, 92.50, 2127.47, 'paid', 'cash', NULL),
('INV-2024-0010', 9, '2024-05-25', '2024-06-25', 2099.98, 420.00, 0.00, 2519.98, 'paid', 'bank_transfer', NULL),
('INV-2024-0011', 10, '2024-06-08', '2024-07-08', 4549.95, 909.99, 227.49, 5232.45, 'paid', 'credit_card', 'Fashion week preparation'),
('INV-2024-0012', 11, '2024-06-22', '2024-07-22', 1299.99, 260.00, 0.00, 1559.99, 'pending', 'bank_transfer', NULL),
('INV-2024-0013', 12, '2024-07-05', '2024-08-05', 15999.85, 3199.97, 799.99, 18399.83, 'paid', 'bank_transfer', 'New office setup'),
('INV-2024-0014', 2, '2024-07-18', '2024-08-18', 2549.97, 509.99, 127.49, 2932.47, 'paid', 'credit_card', 'Quarterly refresh'),
('INV-2024-0015', 5, '2024-08-01', '2024-09-01', 6499.94, 1299.99, 324.99, 7474.94, 'paid', 'bank_transfer', NULL),
('INV-2024-0016', 3, '2024-08-15', '2024-09-15', 899.99, 180.00, 0.00, 1079.99, 'pending', 'bank_transfer', 'Replacement order'),
('INV-2024-0017', 7, '2024-09-02', '2024-10-02', 4999.95, 999.99, 249.99, 5749.95, 'paid', 'bank_transfer', NULL),
('INV-2024-0018', 4, '2024-09-20', '2024-10-20', 1749.97, 350.00, 0.00, 2099.97, 'overdue', 'bank_transfer', 'Payment reminder sent'),
('INV-2024-0019', 6, '2024-10-05', '2024-11-05', 3599.96, 719.99, 179.99, 4139.96, 'pending', 'credit_card', NULL),
('INV-2024-0020', 1, '2024-10-18', '2024-11-18', 2299.98, 459.99, 0.00, 2759.97, 'pending', 'bank_transfer', 'End of year order'),
('INV-2024-0021', 10, '2024-11-01', '2024-12-01', 5899.94, 1179.99, 294.99, 6784.94, 'pending', 'credit_card', 'Black Friday order'),
('INV-2024-0022', 12, '2024-11-15', '2024-12-15', 8999.90, 1799.98, 449.99, 10349.89, 'pending', 'bank_transfer', 'Year-end equipment'),
('INV-2024-0023', 8, '2024-11-28', '2024-12-28', 1099.98, 220.00, 0.00, 1319.98, 'pending', 'cash', NULL),
('INV-2024-0024', 9, '2024-12-10', '2025-01-10', 3449.97, 689.99, 172.49, 3967.47, 'pending', 'bank_transfer', 'Christmas order'),
('INV-2024-0025', 11, '2024-12-20', '2025-01-20', 799.99, 160.00, 0.00, 959.99, 'pending', 'bank_transfer', NULL);

-- =====================================================
-- SAMPLE DATA: Articles (Invoice Line Items)
-- =====================================================
-- Invoice 1: Jean Dupont
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(1, 1, 1, 1299.99, 0.00, 1299.99),
(1, 4, 2, 129.99, 0.00, 259.98),
(1, 5, 2, 79.99, 0.00, 159.98),
(1, 3, 1, 549.99, 0.00, 549.99),
(1, 6, 2, 199.99, 0.00, 399.98);

-- Invoice 2: Marie Martin
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(2, 1, 3, 1299.99, 5.00, 3704.97),
(2, 3, 3, 549.99, 5.00, 1567.47),
(2, 9, 3, 449.99, 5.00, 1282.47);

-- Invoice 3: Ahmed Benali
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(3, 2, 2, 799.99, 0.00, 1599.98);

-- Invoice 4: Sophie Laurent
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(4, 12, 1, 899.99, 5.00, 854.99);

-- Invoice 5: Carlos Rodriguez
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(5, 1, 5, 1299.99, 5.00, 6174.95),
(5, 10, 3, 699.99, 5.00, 1994.97),
(5, 9, 5, 449.99, 5.00, 2137.45);

-- Invoice 6: Emma Wilson
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(6, 1, 2, 1299.99, 0.00, 2599.98),
(6, 4, 2, 129.99, 0.00, 259.98),
(6, 5, 2, 79.99, 0.00, 159.98),
(6, 7, 2, 89.99, 0.00, 179.98);

-- Invoice 7: Hans Mueller
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(7, 1, 8, 1299.99, 5.00, 9879.92),
(7, 3, 8, 549.99, 5.00, 4179.92),
(7, 8, 8, 249.99, 5.00, 1899.92);

-- Invoice 8: Jean Dupont (second order)
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(8, 13, 10, 24.99, 0.00, 249.90),
(8, 14, 15, 19.99, 0.00, 299.85),
(8, 16, 2, 79.99, 0.00, 159.98);

-- Invoice 9: Fatima Zahra
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(9, 2, 1, 799.99, 5.00, 759.99),
(9, 3, 1, 549.99, 5.00, 522.49),
(9, 4, 1, 129.99, 5.00, 123.49),
(9, 5, 1, 79.99, 5.00, 75.99);

-- Invoice 10: Pierre Moreau
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(10, 10, 2, 699.99, 0.00, 1399.98),
(10, 9, 1, 449.99, 0.00, 449.99),
(10, 8, 1, 249.99, 0.00, 249.99);

-- Invoice 11: Isabella Rossi
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(11, 1, 2, 1299.99, 5.00, 2469.98),
(11, 12, 2, 899.99, 5.00, 1709.98),
(11, 6, 3, 199.99, 5.00, 569.97);

-- Invoice 12: Omar Hassan
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(12, 1, 1, 1299.99, 0.00, 1299.99);

-- Invoice 13: Lucie Bernard
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(13, 1, 10, 1299.99, 5.00, 12349.90),
(13, 3, 10, 549.99, 5.00, 5224.90),
(13, 4, 10, 129.99, 5.00, 1234.90),
(13, 5, 10, 79.99, 5.00, 759.90);

-- Invoice 14: Marie Martin (second order)
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(14, 6, 5, 199.99, 5.00, 949.95),
(14, 7, 5, 89.99, 5.00, 427.45),
(14, 8, 3, 249.99, 5.00, 712.47);

-- Invoice 15: Carlos Rodriguez (second order)
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(15, 1, 4, 1299.99, 5.00, 4939.96),
(15, 11, 4, 399.99, 5.00, 1519.96);

-- Invoice 16: Ahmed Benali (second order)
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(16, 12, 1, 899.99, 0.00, 899.99);

-- Invoice 17: Hans Mueller (second order)
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(17, 10, 5, 699.99, 5.00, 3324.95),
(17, 9, 5, 449.99, 5.00, 2137.45);

-- Invoice 18: Sophie Laurent (second order - overdue)
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(18, 2, 1, 799.99, 0.00, 799.99),
(18, 3, 1, 549.99, 0.00, 549.99),
(18, 6, 2, 199.99, 0.00, 399.98);

-- Invoice 19: Emma Wilson (second order)
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(19, 12, 2, 899.99, 5.00, 1709.98),
(19, 17, 10, 89.99, 5.00, 854.90),
(19, 18, 5, 149.99, 5.00, 712.45);

-- Invoice 20: Jean Dupont (third order)
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(20, 19, 2, 299.99, 0.00, 599.98),
(20, 20, 10, 69.99, 0.00, 699.90),
(20, 15, 5, 149.99, 0.00, 749.95);

-- Invoice 21: Isabella Rossi (second order)
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(21, 1, 3, 1299.99, 5.00, 3704.97),
(21, 3, 3, 549.99, 5.00, 1567.47),
(21, 6, 5, 199.99, 5.00, 949.95);

-- Invoice 22: Lucie Bernard (second order)
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(22, 1, 5, 1299.99, 5.00, 6174.95),
(22, 10, 3, 699.99, 5.00, 1994.97),
(22, 9, 5, 449.99, 5.00, 2137.45);

-- Invoice 23: Fatima Zahra (second order)
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(23, 4, 3, 129.99, 0.00, 389.97),
(23, 5, 3, 79.99, 0.00, 239.97),
(23, 7, 2, 89.99, 0.00, 179.98),
(23, 13, 5, 24.99, 0.00, 124.95);

-- Invoice 24: Pierre Moreau (second order)
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(24, 1, 2, 1299.99, 5.00, 2469.98),
(24, 8, 3, 249.99, 5.00, 712.47),
(24, 4, 2, 129.99, 5.00, 246.98);

-- Invoice 25: Omar Hassan (second order)
INSERT INTO articles (invoice_id, product_id, quantity, unit_price, discount_percent, line_total) VALUES
(25, 2, 1, 799.99, 0.00, 799.99);

-- =====================================================
-- Create useful views for reporting
-- =====================================================

-- Customer summary view
CREATE OR REPLACE VIEW customer_summary AS
SELECT 
    c.customer_id,
    c.first_name || ' ' || c.last_name AS full_name,
    c.company,
    c.customer_type,
    COUNT(DISTINCT i.invoice_id) AS total_invoices,
    COALESCE(SUM(i.total_amount), 0) AS total_revenue,
    MAX(i.invoice_date) AS last_order_date
FROM customers c
LEFT JOIN invoices i ON c.customer_id = i.customer_id
GROUP BY c.customer_id, c.first_name, c.last_name, c.company, c.customer_type;

-- Product sales summary view
CREATE OR REPLACE VIEW product_sales_summary AS
SELECT 
    p.product_id,
    p.sku,
    p.name,
    p.category,
    p.unit_price,
    p.stock_quantity,
    COALESCE(SUM(a.quantity), 0) AS total_sold,
    COALESCE(SUM(a.line_total), 0) AS total_revenue
FROM products p
LEFT JOIN articles a ON p.product_id = a.product_id
GROUP BY p.product_id, p.sku, p.name, p.category, p.unit_price, p.stock_quantity;

-- Monthly revenue view
CREATE OR REPLACE VIEW monthly_revenue AS
SELECT 
    DATE_TRUNC('month', invoice_date) AS month,
    COUNT(*) AS invoice_count,
    SUM(total_amount) AS total_revenue,
    AVG(total_amount) AS avg_invoice_value
FROM invoices
WHERE status IN ('paid', 'pending')
GROUP BY DATE_TRUNC('month', invoice_date)
ORDER BY month;

-- Outstanding invoices view
CREATE OR REPLACE VIEW outstanding_invoices AS
SELECT 
    i.invoice_id,
    i.invoice_number,
    c.first_name || ' ' || c.last_name AS customer_name,
    c.company,
    i.invoice_date,
    i.due_date,
    i.total_amount,
    i.status,
    CURRENT_DATE - i.due_date AS days_overdue
FROM invoices i
JOIN customers c ON i.customer_id = c.customer_id
WHERE i.status IN ('pending', 'overdue')
ORDER BY i.due_date;

-- Grant privileges
GRANT ALL PRIVILEGES ON SCHEMA crm TO ai;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA crm TO ai;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA crm TO ai;

-- Ensure default search path includes crm schema permanently
ALTER DATABASE crm SET search_path TO crm, public;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'CRM database schema and sample data initialized successfully';
END $$;
