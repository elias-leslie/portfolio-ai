import os
import sys
from app.storage.facade import PortfolioStorage

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))


def inspect_schema():
    storage = PortfolioStorage()
    with storage.connection() as conn:
        for table in ["idea_outcomes", "agent_ideas"]:
            print(f"\nIndexes on {table}:")
            result = conn.execute(f"""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = '{table}'
            """).fetchall()

            for row in result:
                print(f"- {row[0]}: {row[1]}")


if __name__ == "__main__":
    inspect_schema()
