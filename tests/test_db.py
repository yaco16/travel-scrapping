from datetime import date

from sqlalchemy import select

from travel_scrapping.config import Settings
from travel_scrapping.db import Deal, PriceObservation, SearchRun, init_db, save_deals, session_scope
from travel_scrapping.schemas import DealCandidate


def test_sqlite_persistence(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/x.db")
    factory = init_db(settings)
    deal = DealCandidate(
        source="test",
        origin_airport="NCE",
        destination_airport="BCN",
        outbound_date=date(2026, 7, 1),
        return_date=date(2026, 7, 4),
        nights=3,
        total_price=40,
    )
    with session_scope(factory) as session:
        run = SearchRun(status="completed")
        session.add(run)
        session.flush()
        save_deals(session, run, [deal])
    with session_scope(factory) as session:
        row = session.scalars(select(Deal)).one()
        assert row.destination_airport == "BCN"


def test_two_campaigns_persist_two_price_observations(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/x.db")
    factory = init_db(settings)
    for price in [40, 42]:
        deal = DealCandidate(
            source="test",
            origin_airport="NCE",
            destination_airport="BCN",
            destination_city="Barcelone",
            outbound_date=date(2026, 7, 1),
            return_date=date(2026, 7, 4),
            nights=3,
            total_price=price,
            airlines=["U2"],
            confidence="high",
            raw_payload={"price": price},
        )
        with session_scope(factory) as session:
            run = SearchRun(status="completed")
            session.add(run)
            session.flush()
            save_deals(session, run, [deal])
    with session_scope(factory) as session:
        rows = list(session.scalars(select(PriceObservation).order_by(PriceObservation.id)))
        assert len(rows) == 2
        assert [row.price for row in rows] == [40, 42]
        assert rows[0].run_id != rows[1].run_id
        assert rows[0].destination_city == "Barcelone"
