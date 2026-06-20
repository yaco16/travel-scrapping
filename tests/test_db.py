from datetime import date

from sqlalchemy import func, select

from travel_scrapping.config import Settings
from travel_scrapping.db import (
    Deal,
    PriceObservation,
    SearchRun,
    init_db,
    save_deals,
    session_scope,
    valid_price_observation_clause,
)
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
        airlines=["easyJet"],
            booking_url="https://example.test/book",
            average_price=75,
            discount_percent=33,
            image_url="https://example.test/image.jpg",
        )
    with session_scope(factory) as session:
        run = SearchRun(status="completed")
        session.add(run)
        session.flush()
        inserted = save_deals(session, run, [deal])
        run.accepted_count = inserted
    with session_scope(factory) as session:
        row = session.scalars(select(Deal)).one()
        assert row.destination_airport == "BCN"
        assert row.run_id == 1
        assert row.average_price == 75
        assert row.discount_percent == 33
        assert row.image_url == "https://example.test/image.jpg"
        observation = session.scalars(select(PriceObservation)).one()
        assert observation.run_id == 1
        assert observation.observed_at is not None
        assert observation.source == "test"
        assert observation.origin_iata == "NCE"
        assert observation.destination_iata == "BCN"
        assert observation.destination_city == "BCN"
        assert observation.departure_date == date(2026, 7, 1)
        assert observation.return_date == date(2026, 7, 4)
        assert observation.nights == 3
        assert observation.price == 40
        assert observation.currency == "EUR"
        assert observation.airline == "easyJet"
        assert observation.confidence == "low"
        assert observation.warnings == "[]"
        assert observation.raw_payload_hash is not None
        assert row.run.accepted_count == 1


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
            booking_url="https://example.test/book",
            confidence="high",
            raw_payload={"price": price},
        )
        with session_scope(factory) as session:
            run = SearchRun(status="completed")
            session.add(run)
            session.flush()
            inserted = save_deals(session, run, [deal])
            run.accepted_count = inserted
    with session_scope(factory) as session:
        rows = list(session.scalars(select(PriceObservation).order_by(PriceObservation.id)))
        assert len(rows) == 2
        assert [row.price for row in rows] == [40, 42]
        assert rows[0].run_id != rows[1].run_id
        assert rows[0].destination_city == "Barcelone"
        assert session.scalar(select(func.count(PriceObservation.id)).where(valid_price_observation_clause())) == 2


def test_save_deals_skips_missing_required_observation_fields(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/x.db")
    factory = init_db(settings)
    deal = DealCandidate(
        source="test",
        origin_airport="",
        destination_airport="BCN",
        outbound_date=date(2026, 7, 1),
        return_date=date(2026, 7, 4),
        nights=3,
        total_price=40,
        airlines=["easyJet"],
        booking_url="https://example.test/book",
    )
    with session_scope(factory) as session:
        run = SearchRun(status="completed")
        session.add(run)
        session.flush()
        inserted = save_deals(session, run, [deal])
        run.accepted_count = inserted
    with session_scope(factory) as session:
        assert session.query(Deal).count() == 0
        assert session.query(PriceObservation).count() == 0
        assert session.scalars(select(SearchRun)).one().accepted_count == 0
