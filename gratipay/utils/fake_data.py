"""This module contains utilities for populating a non-production environment with fake data.
"""
import datetime
from decimal import Decimal as D
import random
import string
import sys

from faker import Factory
from psycopg2 import IntegrityError

from gratipay import wireup, MAX_TIP, MIN_TIP
from gratipay.elsewhere import PLATFORMS
from gratipay.models.participant import Participant
from gratipay.models.team import slugize, Team
from gratipay.models import community
from gratipay.models import check_db

faker = Factory.create()


def insert_fake_data(db, tablename, **kw):
    """Insert fake data into the database.

    :param Postgres db: a ``Postgres`` or ``Cursor`` object
    :param unicode tablename: the name of the table to insert into
    :param dict **kw: a mapping of column names to values

    """
    column_names = []
    column_value_placeholders = []
    column_values = []

    for k,v in kw.items():
        column_names.append(k)
        column_value_placeholders.append("%s")
        column_values.append(v)

    column_names = ", ".join(column_names)
    column_value_placeholders = ", ".join(column_value_placeholders)

    db.run( "INSERT INTO {} ({}) VALUES ({})"
            .format(tablename, column_names, column_value_placeholders)
          , column_values
           )
    return kw


def fake_text_id(size=6, chars=string.ascii_lowercase + string.digits):
    """Create a random text id.
    """
    return ''.join(random.choice(chars) for x in range(size))


def fake_sentence(start=1, stop=100):
    """Create a sentence of random length.
    """
    return faker.sentence(random.randrange(start,stop))


def fake_participant(db, is_admin=False, random_identities=True):
    """Create a fake User.

    :param Postgres db: a ``Postgres`` or ``Cursor`` object
    :param bool is_admin: whether to make the participant an admin
    :param bool random_identities: whether to give the participant random identities

    """
    username = faker.first_name() + fake_text_id(3)
    try:
        insert_fake_data( db
                        , "participants"
                        , username=username
                        , username_lower=username.lower()
                        , ctime=faker.date_time_this_year()
                        , is_admin=is_admin
                        , balance=0
                        , anonymous_giving=(random.randrange(5) == 0)
                        , balanced_customer_href=faker.uri()
                        , is_suspicious=False
                        , claimed_time=faker.date_time_this_year()
                        , email_address='{}@example.com'.format(username)
                         )
        participant = Participant.from_username(username)

        if random_identities:
            if random.randrange(100) < 66:
                fake_participant_identity(participant)
                if random.randrange(100) < 33:
                    fake_participant_identity(participant)
                    if random.randrange(100) < 50:
                        fake_participant_identity(participant)

    except IntegrityError:
        return fake_participant(db, is_admin)

    return participant


def fake_participant_identity(participant, verification=None):
    """Pick a country and make an identity for the participant there.

    :param Participant participant: a participant object
    :param bool verification: the value to set verification to; None will result in a 50% chance
        either way
    :returns: a country id

    """
    country_id = random_country_id(participant.db)
    participant.store_identity_info(country_id, 'nothing-enforced', {})
    if verification:
        participant.set_identity_verification(country_id, verification)
    elif (random.randrange(2) == 0):   # 50%
        participant.set_identity_verification(country_id, True)
    return country_id


def fake_team(db, teamowner):
    """Create a fake team
    """
    isapproved = [True, False]
    productorservice = ['Product','Service']

    teamname = faker.first_name() + fake_text_id(3)
    teamslugname = faker.city()

    try:
        teamslug = slugize(teamslugname)
        homepage = 'http://www.example.org/' + fake_text_id(3)
        insert_fake_data( db
                        , "teams"
                        , slug=teamslug
                        , slug_lower=teamslug.lower()
                        , name=teamname
                        , homepage=homepage
                        , product_or_service=random.sample(productorservice,1)[0]
                        , todo_url=homepage + '/tickets'
                        , onboarding_url=homepage + '/contributing'
                        , owner=teamowner.username
                        , is_approved=random.sample(isapproved,1)[0]
                        , receiving=0.1
                        , nreceiving_from=3
                         )
    except IntegrityError:
        return fake_team(db, teamowner)

    return Team.from_slug(teamslug)


def fake_payment_instruction(db, participant, team):
    """Create a fake payment_instruction
    """
    return insert_fake_data( db
                           , "payment_instructions"
                           , ctime=faker.date_time_this_year()
                           , mtime=faker.date_time_this_month()
                           , participant_id=participant.id
                           , team_id=team.id
                           , amount=fake_tip_amount()
                            )


def fake_community(db, creator):
    """Create a fake community
    """
    name = faker.city()
    if not community.name_pattern.match(name):
        return fake_community(db, creator)

    slug = community.slugize(name)

    creator.insert_into_communities(True, name, slug)

    return community.Community.from_slug(slug)


def fake_tip_amount():
    amount = ((D(random.random()) * (MAX_TIP - MIN_TIP))
            + MIN_TIP)

    decimal_amount = D(amount).quantize(D('.01'))
    while decimal_amount == D('0.00'):
        # https://github.com/gratipay/gratipay.com/issues/2950
        decimal_amount = fake_tip_amount()
    return decimal_amount


def fake_tip(db, tipper, tippee):
    """Create a fake tip.
    """
    return insert_fake_data( db
                           , "tips"
                           , ctime=faker.date_time_this_year()
                           , mtime=faker.date_time_this_month()
                           , tipper=tipper.username
                           , tippee=tippee.username
                           , amount=fake_tip_amount()
                            )


def fake_elsewhere(db, participant, platform):
    """Create a fake elsewhere.
    """
    insert_fake_data( db
                    , "elsewhere"
                    , platform=platform
                    , user_id=fake_text_id()
                    , user_name=participant.username
                    , participant=participant.username
                    , extra_info=None
                     )


def fake_transfer(db, tipper, tippee):
    return insert_fake_data( db
                           , "transfers"
                           , timestamp=faker.date_time_this_year()
                           , tipper=tipper.username
                           , tippee=tippee.username
                           , amount=fake_tip_amount()
                           , context='tip'
                            )


def fake_exchange(db, participant, amount, fee, timestamp):
    return insert_fake_data( db
                           , "exchanges"
                           , timestamp=timestamp
                           , participant=participant.username
                           , amount=amount
                           , fee=fee
                           , status='succeeded'
                            )


def random_country_id(db):
    return db.one("SELECT id FROM countries ORDER BY random() LIMIT 1")


def prep_db(db):
    db.run("""
        CREATE OR REPLACE FUNCTION process_transfer() RETURNS trigger AS $$
            BEGIN
                UPDATE participants
                   SET balance = balance + NEW.amount
                 WHERE username = NEW.tippee;

                UPDATE participants
                   SET balance = balance - NEW.amount
                 WHERE username = NEW.tipper;

                RETURN NULL;
            END;
        $$ language plpgsql;

        CREATE TRIGGER process_transfer AFTER INSERT ON transfers
            FOR EACH ROW EXECUTE PROCEDURE process_transfer();

        CREATE OR REPLACE FUNCTION process_exchange() RETURNS trigger AS $$
            BEGIN
                IF NEW.amount > 0 THEN
                    UPDATE participants
                       SET balance = balance + NEW.amount
                     WHERE username = NEW.participant;
                ELSE
                    UPDATE participants
                       SET balance = balance + NEW.amount - NEW.fee
                     WHERE username = NEW.participant;
                END IF;

                RETURN NULL;
            END;
        $$ language plpgsql;

        CREATE TRIGGER process_exchange AFTER INSERT ON exchanges
            FOR EACH ROW EXECUTE PROCEDURE process_exchange();
    """)


def clean_db(db):
    db.run("""
        DROP FUNCTION IF EXISTS process_transfer() CASCADE;
        DROP FUNCTION IF EXISTS process_exchange() CASCADE;
    """)


def populate_db(db, num_participants=100, ntips=200, num_teams=5, num_transfers=5000, num_communities=20):
    """Populate DB with fake data.
    """
    print("Making Participants")
    make_flag_tester = num_participants > 1

    participants = []
    for i in xrange(num_participants - 1 if make_flag_tester else num_participants):
        participants.append(fake_participant(db))

    if make_flag_tester:
        # make a participant for testing weird flags
        flag_tester = fake_participant(db, random_identities=False)
        participants.append(flag_tester)

        nepal = db.one("SELECT id FROM countries WHERE code='NP'")
        flag_tester.store_identity_info(nepal, 'nothing-enforced', {})
        flag_tester.set_identity_verification(nepal, True)

        vatican = db.one("SELECT id FROM countries WHERE code='VA'")
        flag_tester.store_identity_info(vatican, 'nothing-enforced', {})
        flag_tester.set_identity_verification(vatican, True)

    print("Making Teams")
    teams = []
    teamowners = random.sample(participants, num_teams)
    for teamowner in teamowners:
        teams.append(fake_team(db, teamowner))

    print("Making Payment Instructions")
    npayment_instructions = 0
    for participant in participants:
        for team in teams:
            #eliminate self-payment
            if participant.username != team.owner:
                npayment_instructions += 1
                if npayment_instructions > ntips:
                    break
                fake_payment_instruction(db, participant, team)
        if npayment_instructions > ntips:
            break


    print("Making Elsewheres")
    for p in participants:
        #All participants get between 1 and 3 elsewheres
        num_elsewheres = random.randint(1, 3)
        for platform_name in random.sample(PLATFORMS, num_elsewheres):
            fake_elsewhere(db, p, platform_name)

    print("Making Communities")
    for i in xrange(num_communities):
        creator = random.sample(participants, 1)
        community = fake_community(db, creator[0])

        members = random.sample(participants, random.randint(1, 3))
        for p in members:
            p.insert_into_communities(True, community.name, community.slug)

    print("Making Tips")
    tips = []
    for i in xrange(ntips):
        tipper, tippee = random.sample(participants, 2)
        tips.append(fake_tip(db, tipper, tippee))

    # Transfers
    transfers = []
    for i in xrange(num_transfers):
        sys.stdout.write("\rMaking Transfers (%i/%i)" % (i+1, num_transfers))
        sys.stdout.flush()
        tipper, tippee = random.sample(participants, 2)
        transfers.append(fake_transfer(db, tipper, tippee))
    print("")

    # Paydays
    # First determine the boundaries - min and max date
    min_date = min(min(x['ctime'] for x in tips), \
                   min(x['timestamp'] for x in transfers))
    max_date = max(max(x['ctime'] for x in tips), \
                   max(x['timestamp'] for x in transfers))
    # iterate through min_date, max_date one week at a time
    payday_counter = 1
    date = min_date
    paydays_total = (max_date - min_date).days/7 + 1
    while date < max_date:
        sys.stdout.write("\rMaking Paydays (%i/%i)" % (payday_counter, paydays_total))
        sys.stdout.flush()
        payday_counter += 1
        end_date = date + datetime.timedelta(days=7)
        week_tips = filter(lambda x: date < x['ctime'] < end_date, tips)
        week_transfers = filter(lambda x: date < x['timestamp'] < end_date, transfers)
        week_participants = filter(lambda x: x.ctime.replace(tzinfo=None) < end_date, participants)
        for p in week_participants:
            transfers_in = filter(lambda x: x['tippee'] == p.username, week_transfers)
            transfers_out = filter(lambda x: x['tipper'] == p.username, week_transfers)
            amount_in = sum([t['amount'] for t in transfers_in])
            amount_out = sum([t['amount'] for t in transfers_out])
            amount = amount_out - amount_in
            if amount != 0:
                fee = amount * D('0.02')
                fee = abs(fee.quantize(D('.01')))
                fake_exchange(
                    db=db,
                    participant=p,
                    amount=amount,
                    fee=fee,
                    timestamp=(end_date - datetime.timedelta(seconds=1))
                )
        actives=set()
        tippers=set()
        for xfers in week_tips, week_transfers:
            actives.update(x['tipper'] for x in xfers)
            actives.update(x['tippee'] for x in xfers)
            tippers.update(x['tipper'] for x in xfers)
        payday = {
            'ts_start': date,
            'ts_end': end_date,
            'nusers': len(actives),
            'volume': sum(x['amount'] for x in week_transfers)
        }
        insert_fake_data(db, "paydays", **payday)
        date = end_date
    print("")


def _wireup():
    env = wireup.env()
    db = wireup.db(env)
    wireup.crypto(env)
    return db


def main(db=None, *a, **kw):
    db = db or _wireup()
    clean_db(db)
    prep_db(db)
    populate_db(db, *a, **kw)
    clean_db(db)
    check_db(db)


if __name__ == '__main__':
    main()
