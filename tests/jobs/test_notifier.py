import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock

from oventime.cache import cache
from oventime.jobs.notifier import Notifier
from oventime.config import LEAF_THRESHOLD, FIRE_THRESHOLD
from oventime.utils import floor_dt


# ── Fixture ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    cache.DB_PATH = tmp_path / "cache.sqlite"
    cache.init_db()


def insert_diag(score, minutes_offset=0):
    """Insère un diagnostic avec un score donné dans le cache."""
    ts = floor_dt(datetime.now(timezone.utc)) + timedelta(minutes=minutes_offset)
    cache.save({
        "time": ts,
        "status": "green",
        "score": score,
        "nuclear_bonus": 0.0,
        "ocgt_malus": 0.0,
        "gasCCG_use_rate": 0.2,
        "gasCCG_phase": 0.3,
        "storage_phase": 0.1,
        "storage_use_rate": 0.15,
        "nuclear_use_rate": 0.8,
        "nextwind_start": ts,
        "nextwind_end": ts + timedelta(hours=1),
        "nextwind_method": "otsu",
    })


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch.object(Notifier, "_notify_web", new_callable=AsyncMock)
@patch.object(Notifier, "_notify_telegram", new_callable=AsyncMock)
async def test_no_alert_when_score_normal(mock_tg, mock_web):
    """Score entre les seuils → aucune alerte envoyée."""
    insert_diag(score=50)
    n = Notifier()
    await n.check_and_notify()

    mock_tg.assert_not_called()
    mock_web.assert_not_called()


@pytest.mark.asyncio
@patch.object(Notifier, "_notify_web", new_callable=AsyncMock)
@patch.object(Notifier, "_notify_telegram", new_callable=AsyncMock)
async def test_alert_on_abundance(mock_tg, mock_web):
    """Score au-dessus de LEAF_THRESHOLD → alerte abondance."""
    insert_diag(score=LEAF_THRESHOLD + 10)
    n = Notifier()
    await n.check_and_notify()

    mock_tg.assert_called_once()
    mock_web.assert_called_once()
    assert n.last_alert_high is True


@pytest.mark.asyncio
@patch.object(Notifier, "_notify_web", new_callable=AsyncMock)
@patch.object(Notifier, "_notify_telegram", new_callable=AsyncMock)
async def test_alert_on_tension(mock_tg, mock_web):
    """Score en-dessous de FIRE_THRESHOLD → alerte tension."""
    insert_diag(score=FIRE_THRESHOLD - 5)
    n = Notifier()
    await n.check_and_notify()

    mock_tg.assert_called_once()
    mock_web.assert_called_once()
    assert n.last_alert_low is True


@pytest.mark.asyncio
@patch.object(Notifier, "_notify_web", new_callable=AsyncMock)
@patch.object(Notifier, "_notify_telegram", new_callable=AsyncMock)
async def test_no_duplicate_alert(mock_tg, mock_web):
    """Même timestamp vu deux fois → pas de double alerte."""
    insert_diag(score=LEAF_THRESHOLD + 10)
    n = Notifier()

    await n.check_and_notify()
    await n.check_and_notify()

    assert mock_tg.call_count == 1


@pytest.mark.asyncio
@patch.object(Notifier, "_notify_web", new_callable=AsyncMock)
@patch.object(Notifier, "_notify_telegram", new_callable=AsyncMock)
async def test_return_to_normal_after_abundance(mock_tg, mock_web):
    """Score redescend sous LEAF → alerte 'retour à la normale'."""
    insert_diag(score=LEAF_THRESHOLD + 10, minutes_offset=-30)
    n = Notifier()
    await n.check_and_notify()
    assert n.last_alert_high is True

    insert_diag(score=50, minutes_offset=-15)
    await n.check_and_notify()
    assert n.last_alert_high is False
    assert mock_tg.call_count == 2


@pytest.mark.asyncio
@patch.object(Notifier, "_notify_web", new_callable=AsyncMock)
@patch.object(Notifier, "_notify_telegram", new_callable=AsyncMock)
async def test_no_alert_when_cache_empty(mock_tg, mock_web):
    """Cache vide → rien ne se passe, pas d'erreur."""
    n = Notifier()
    await n.check_and_notify()

    mock_tg.assert_not_called()
    mock_web.assert_not_called()
