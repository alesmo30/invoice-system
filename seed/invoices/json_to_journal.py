#!/usr/bin/env python3
"""
Script to transform JSON invoice data into Spanish daily journals for RAG system.
Follows the specifications from journal.txt prompt.
"""

import json
import os
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any

def load_json_data(file_path: str) -> Dict[str, Any]:
    """Load JSON data from file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def format_currency(amount: str) -> str:
    """Format currency amount for Spanish text."""
    amount_int = int(amount)
    return f"${amount_int:,}".replace(',', '.')

def get_date_in_spanish(date_str: str) -> str:
    """Convert date to Spanish format."""
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    months = {
        1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
        5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
        9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
    }
    return f"{date_obj.day} de {months[date_obj.month]} de {date_obj.year}"

def wrap_text_to_80(text: str) -> str:
    """Wrap text to maximum 80 characters per line."""
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        if len(test_line) <= 80:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    
    if current_line:
        lines.append(current_line)
    
    return '\n'.join(lines)

def group_invoices_by_employee(data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Group invoices by employee."""
    employee_invoices = defaultdict(list)
    
    for invoice_id, invoice_data in data.items():
        employee_id = invoice_data['employee']['id']
        employee_invoices[employee_id].append(invoice_data)
    
    return employee_invoices

def calculate_employee_totals(invoices: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate totals and statistics for an employee."""
    total_amount = 0
    products_sold = []
    customers_served = set()
    
    for invoice in invoices:
        total_amount += int(invoice['total_amount'])
        customer_name = f"{invoice['customer']['first_name']} {invoice['customer']['last_name']}"
        customers_served.add(customer_name)
        
        for item in invoice['items']:
            products_sold.append({
                'name': item['product']['name'],
                'category': item['product']['category'],
                'quantity': item['quantity'],
                'unit_price': int(item['unit_price']),
                'line_total': int(item['line_total']),
                'customer': customer_name
            })
    
    return {
        'total_amount': total_amount,
        'products_sold': products_sold,
        'customers_served': list(customers_served),
        'num_invoices': len(invoices)
    }

def generate_employee_section(employee_data: Dict[str, Any], employee_stats: Dict[str, Any], date_str: str = None) -> str:
    """Generate the Spanish text section for an employee."""
    employee = employee_data['employee']
    employee_name = f"{employee['first_name']} {employee['last_name']}"
    employee_id = employee['id']
    
    # Start employee section with optional date
    text = ""
    if date_str:
        text = f"{date_str}\n\n"
    text += f"{employee_name} ({employee_id}):\n\n"
    
    # Products sold section
    products_by_category = defaultdict(list)
    for product in employee_stats['products_sold']:
        products_by_category[product['category']].append(product)
    
    paragraph = "Durante esta jornada laboral se registraron las siguientes ventas: "
    
    category_descriptions = []
    for category, products in products_by_category.items():
        total_category_amount = sum(p['line_total'] for p in products)
        product_count = sum(p['quantity'] for p in products)
        
        if category == "iPhone":
            category_descriptions.append(f"{product_count} dispositivos iPhone por un valor total de {format_currency(str(total_category_amount))}")
        elif category == "iPad":
            category_descriptions.append(f"{product_count} tablets iPad por un valor total de {format_currency(str(total_category_amount))}")
        elif category == "Mac":
            category_descriptions.append(f"{product_count} computadoras Mac por un valor total de {format_currency(str(total_category_amount))}")
        elif category == "Accessories":
            category_descriptions.append(f"{product_count} accesorios por un valor total de {format_currency(str(total_category_amount))}")
    
    paragraph += ", ".join(category_descriptions) + ". "
    
    # Customers served section
    if len(employee_stats['customers_served']) == 1:
        paragraph += f"El cliente atendido durante el día fue {employee_stats['customers_served'][0]}. "
    else:
        customers_list = ", ".join(employee_stats['customers_served'][:-1])
        last_customer = employee_stats['customers_served'][-1]
        paragraph += f"Los clientes atendidos durante el día fueron {customers_list} y {last_customer}. "
    
    # Detailed sales breakdown
    paragraph += "El desglose detallado de las transacciones incluye: "
    
    sale_details = []
    for i, product in enumerate(employee_stats['products_sold'], 1):
        if product['quantity'] > 1:
            sale_details.append(f"la venta de {product['quantity']} unidades de {product['name']} a {product['customer']} por {format_currency(str(product['line_total']))}")
        else:
            sale_details.append(f"la venta de {product['name']} a {product['customer']} por {format_currency(str(product['line_total']))}")
    
    paragraph += ", ".join(sale_details) + ". "
    
    # Total amount section
    paragraph += f"El monto total de ventas generadas por {employee_name} durante esta jornada fue de {format_currency(str(employee_stats['total_amount']))} a través de {employee_stats['num_invoices']} transacciones comerciales."
    
    # Wrap the paragraph to 80 characters
    wrapped_paragraph = wrap_text_to_80(paragraph)
    text += wrapped_paragraph + "\n\n"
    
    return text

def transform_json_to_journal(json_file_path: str) -> str:
    """Transform JSON invoice data to Spanish daily journal."""
    data = load_json_data(json_file_path)
    
    # Get the date from the first invoice
    first_invoice = next(iter(data.values()))
    date_str = first_invoice['invoice_date']
    spanish_date = get_date_in_spanish(date_str)
    
    # Group invoices by employee
    employee_invoices = group_invoices_by_employee(data)
    
    # Generate section for each employee (each with date prefix)
    journal_sections = []
    for employee_id, invoices in employee_invoices.items():
        employee_stats = calculate_employee_totals(invoices)
        employee_section = generate_employee_section(invoices[0], employee_stats, spanish_date)
        journal_sections.append(employee_section)
    
    # Join all sections with double newline separator
    journal_text = "\n".join(journal_sections)
    
    return journal_text.strip()

def process_all_json_files():
    """Process all JSON files in the daily_data directory."""
    input_dir = "seed/invoices/daily_data"
    output_dir = "seed/invoices/daily-journal"
    
    if not os.path.exists(input_dir):
        print(f"Error: Input directory {input_dir} does not exist")
        return
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    json_files = [f for f in os.listdir(input_dir) if f.endswith('.json')]
    
    for json_file in sorted(json_files):
        input_path = os.path.join(input_dir, json_file)
        
        # Generate output filename (replace .json with .txt)
        output_filename = json_file.replace('.json', '.txt')
        output_path = os.path.join(output_dir, output_filename)
        
        try:
            print(f"Processing {json_file}...")
            journal_text = transform_json_to_journal(input_path)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(journal_text)
            
            print(f"Generated {output_filename}")
            
        except Exception as e:
            print(f"Error processing {json_file}: {str(e)}")

if __name__ == "__main__":
    process_all_json_files()