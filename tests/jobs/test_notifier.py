import pytest
import pandas as pd
from unittest.mock import patch, AsyncMock

from oventime.cache import cache
from oventime.jobs.notifier import Notifier
from oventime.config import LEAF_THRESHOLD, FIRE_THRESHOLD


# ── Fixture ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    cache.DB_PATH = tmp_path / "cache.sqlite"
    cache.init_db()


def insert_diag(score, minutes_offset=0):
    """Insère un diagnostic avec un score donné dans le cache."""
    ts = pd.Timestamp.now(tz="UTC").floor("15min") + pd.Timedelta(minutes=minutes_offset)
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
        "nextwind_end": ts + pd.Timedelta(hours=1),
        "nextwind_method": "otsu",
    })


# ── Tests ────────────────────────────────────────────────────────────────────

# On "patche" les deux méthodes d'envoi pour ne jamais envoyer de vrais
# messages pendant les tests. AsyncMock simule une fonction async.

@pytest.mark.asyncio
@patch.object(Notifier, "_notify_web", new_callable=AsyncMock)
@patch.object(Notifier, "_notify_telegram", new_callable=AsyncMock)
async def test_no_alert_when_score_normal(mock_tg, mock_web):
    """Score entre les seuils → aucune alerte envoyée."""
    insert_diag(score=50)  # entre FIRE (10) et LEAF (100)
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

    mock_tg.assert_called_once()   # un message Telegram envoyé
    mock_web.assert_called_once()  # un web push envoyé
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

    await n.check_and_notify()  # 1ère fois → alerte
    await n.check_and_notify()  # 2ème fois, même ts → rien

    assert mock_tg.call_count == 1  # toujours 1, pas 2


@pytest.mark.asyncio
@patch.object(Notifier, "_notify_web", new_callable=AsyncMock)
@patch.object(Notifier, "_notify_telegram", new_callable=AsyncMock)
async def test_return_to_normal_after_abundance(mock_tg, mock_web):
    """Score redescend sous LEAF → alerte 'retour à la normale'."""
    # 1. Score haut → alerte abondance
    insert_diag(score=LEAF_THRESHOLD + 10, minutes_offset=-30)
    n = Notifier()
    await n.check_and_notify()
    assert n.last_alert_high is True

    # 2. Score redescend → alerte retour à la normale
    insert_diag(score=50, minutes_offset=-15)
    await n.check_and_notify()
    assert n.last_alert_high is False
    assert mock_tg.call_count == 2  # 2 alertes au total


@pytest.mark.asyncio
@patch.object(Notifier, "_notify_web", new_callable=AsyncMock)
@patch.object(Notifier, "_notify_telegram", new_callable=AsyncMock)
async def test_no_alert_when_cache_empty(mock_tg, mock_web):
    """Cache vide → rien ne se passe, pas d'erreur."""
    n = Notifier()
    await n.check_and_notify()

    mock_tg.assert_not_called()
    mock_web.assert_not_called()
