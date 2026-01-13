from app.storage.facade import PortfolioStorage
from app.logging_config import get_logger

logger = get_logger(__name__)

def add_index():
    storage = PortfolioStorage()
    index_name = "idx_outcomes_entry_date"
    table_name = "idea_outcomes"
    column_name = "entry_date"

    with storage.connection() as conn:
        # Check if index exists
        exists = conn.execute(f"""
            SELECT 1
            FROM pg_indexes
            WHERE indexname = '{index_name}'
        """).fetchone()

        if exists:
            logger.info(f"Index {index_name} already exists.")
            return

        logger.info(f"Creating index {index_name} on {table_name}({column_name})...")
        conn.execute(f"""
            CREATE INDEX {index_name}
            ON {table_name} ({column_name} DESC)
        """)
        conn.commit()
        logger.info("Index created successfully.")

if __name__ == "__main__":
    add_index()
