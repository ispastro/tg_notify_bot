from db.session import Sessionlocal
from db.models import User, Batch
from datetime import datetime

def test_db():
    db = Sessionlocal()

    # 1. Create a test batch
    batch = Batch(name="1st year")
    db.add(batch)
    db.commit()

    # 2. Add a test user linked to that batch
    user = User(
        user_id=123456,
        username="test_user",
        batch_id=batch.id,
        join_date=datetime.utcnow()
    )
    db.add(user)
    db.commit()

    # 3. Query and print results
    users = db.query(User).all()
    for u in users:
        print(u.username, u.batch.name)

    db.close()

if __name__ == "__main__":
    test_db()
