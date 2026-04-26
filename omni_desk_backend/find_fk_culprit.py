import os
import sqlite3


def find_all_foreign_keys():
    """
    Connects to the SQLite database, iterates through all tables,
    and prints all foreign key relationships.
    """
    # The db.sqlite3 file is in the same directory as manage.py
    db_path = os.path.join(os.path.dirname(__file__), 'db.sqlite3')
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        return None  # Return None to indicate failure

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    print("--- Foreign Key Relationships ---")
    found_any = False
    for table_tuple in tables:
        table_name = table_tuple[0]
        cursor.execute(f"PRAGMA foreign_key_list('{table_name}');")
        foreign_keys = cursor.fetchall()

        if foreign_keys:
            found_any = True
            print(f"\nTable: '{table_name}'")
            for fk in foreign_keys:
                # fk format: id, seq, table, from, to, on_update, on_delete, match
                from_col = fk[3]
                to_table = fk[2]
                to_col = fk[4]
                print(f"  - Column '{from_col}' -> '{to_table}'('{to_col}')")

    if not found_any:
        print("No foreign key relationships found in the database.")
    print("\n--- End of Report ---")
    return conn  # Return connection for reuse

def find_all_triggers(conn):
    """
    Prints all triggers in the database using the provided connection.
    """
    if not conn:
        return

    cursor = conn.cursor()
    cursor.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type = 'trigger';")
    triggers = cursor.fetchall()

    print("\n--- Trigger Definitions ---")
    if triggers:
        for trigger in triggers:
            print(f"\nTrigger: '{trigger[0]}' on table '{trigger[1]}'")
            print(f"SQL: {trigger[2]}")
    else:
        print("No triggers found in the database.")
    print("\n--- End of Trigger Report ---")


if __name__ == "__main__":
    db_conn = find_all_foreign_keys()
    if db_conn:
        find_all_triggers(db_conn)
        db_conn.close()
