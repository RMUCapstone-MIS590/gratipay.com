from gratipay.wireup import db, env
from gratipay.models.team import migrate_all_tips

db = db(env())

if __name__ == '__main__':
    migrate_all_tips(db)
