import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from app.storage.facade import PortfolioStorage

def cleanup_confidence_scores():
    storage = PortfolioStorage()

    print("Checking for anomalous confidence scores...")

    # Find bad records
    query = "SELECT id, title, confidence_score FROM agent_ideas WHERE confidence_score > 1.0"
    results = storage.query(query)

    if results.is_empty():
        print("No anomalous confidence scores found.")
        return

    bad_records = results.to_dicts()
    print(f"Found {len(bad_records)} records with confidence_score > 1.0")

    # Update records
    count = 0
    with storage.connection() as conn:
        for record in bad_records:
            old_score = float(record["confidence_score"])
            new_score = old_score / 100.0

            # Ensure it's within 0-1 range (handle 7000 case -> 70 -> 0.7)
            while new_score > 1.0:
                new_score /= 100.0

            print(f"Fixing {record['title']}: {old_score} -> {new_score}")

            conn.execute(
                "UPDATE agent_ideas SET confidence_score = %s WHERE id = %s",
                [new_score, record["id"]]
            )
            count += 1
        conn.commit()

    print(f"Successfully fixed {count} records.")

if __name__ == "__main__":
    cleanup_confidence_scores()
