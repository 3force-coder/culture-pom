"""
Script pour récupérer le schéma complet de la base PostgreSQL
Exécuter : python get_schema.py
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

# Forcer l'encodage UTF-8 sur Windows
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# DATABASE_URL depuis Heroku
DATABASE_URL = "postgresql://u8fafht88lvtnt:p42c6cb90faa6ceaa84b011769f50aee9e2af1272183236e9df633d514e1cd797@c56ek37a3ak9jo.cluster-czz5s0kz4scl.eu-west-1.rds.amazonaws.com:5432/dfe2dfrd3gcho5"

def get_all_tables():
    """Récupère la liste de toutes les tables"""
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    
    tables = [row['table_name'] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    
    return tables

def get_table_schema(table_name):
    """Récupère le schéma d'une table"""
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT 
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position;
    """, (table_name,))
    
    columns = cursor.fetchall()
    
    try:
        cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
        count = cursor.fetchone()['count']
    except:
        count = "N/A"
    
    cursor.close()
    conn.close()
    
    return columns, count

def main():
    print("=" * 80)
    print("SCHEMA COMPLET DE LA BASE DE DONNEES - CULTURE POM")
    print("=" * 80)
    print()
    
    tables = get_all_tables()
    
    print(f"Nombre de tables : {len(tables)}")
    print()
    
    for table in tables:
        print("-" * 80)
        print(f"TABLE : {table}")
        print("-" * 80)
        
        columns, count = get_table_schema(table)
        
        print(f"Nombre de lignes : {count}")
        print()
        print("Colonnes :")
        
        for col in columns:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            length = f"({col['character_maximum_length']})" if col['character_maximum_length'] else ""
            default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
            
            print(f"  - {col['column_name']:30} {col['data_type']}{length:15} {nullable}{default}")
        
        print()
    
    print("=" * 80)
    print("Schema recupere avec succes !")
    print("=" * 80)

if __name__ == "__main__":
    main()