"""btc-race-24h: a long-only cbBTC trend bot for agent-fun/bars-replay/v1.

Strategy (designed from first principles for a 24h, 1-minute-bar race):

The replay is long-only, cash earns nothing, and a full-size round trip costs
about 26 bps in fees, slippage and price impact. One-minute BTC noise is
roughly 8 bps (standard deviation), so chasing every wiggle bleeds fees and
every fast exit tested in backtests made things worse: exits on EMA crosses,
on closes below a moving average, or on tight stop-losses all produced more
trades and lower PnL on every scenario tried (dev window, its time-reverse,
drifted-up/down variants, flat and crashing random walks). The design that
survived is deliberately slow and quiet:

* ENTER, with the whole cash balance, only when the trend is confirmed on
  two horizons at once: the 12-bar EMA is above the 96-bar EMA *and* the
  60-bar return is at least +40 bps. Either condition alone fires constantly
  in sideways chop; together they fire rarely, near the start of a real
  move. After an exit, wait 30 bars before re-entering.
* EXIT on a single wide trailing stop: sell everything when the close falls
  250 bps (2.5%) below the highest close seen since entry. That is wide
  enough to survive ordinary chop and tight enough to cap a false entry at
  about one stop-out.
* DAILY LOSS CAP: if equity ever falls $35 below the $1,000 start, sell
  everything and stop trading for the rest of the window. One stop-out
  costs about $25-28, so the cap only binds after the bot has already been
  wrong more than once; it bounds the worst day at roughly -$37 instead of
  letting dead-cat bounces bleed the account in a crash.
* If the market trends down, the entry conditions simply never fire and the
  bot stays in cash. It cannot profit from a falling market, but it does
  not have to: holding cash through a fall is the correct long-only answer.

No randomness, no clock, no environment reads, no network: every decision
is a pure function of the bars the harness sent. The bot answers every
batch with at most one order.

Protocol notes (see kit RULES.txt / protocol.schema.json):
* Orders decided on the batch of the bar closing at minute t fill at the
  open of the next bar, so entries and exits are always one bar late.
* max_slippage_bps is measured from the latest close: buys are capped at
  100 bps so a gap-up open cannot fill far above the signal close; sells
  at 200 bps so a falling market rarely rejects the exit (a rejected exit
  is simply re-sent on the next batch while the stop condition holds).
* A buy spends the whole cash balance; a sell empties the whole position.
  Both clear the $1 minimum notional by construction.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"

# --- strategy parameters (all in bars / basis points) -----------------------
FAST_EMA_BARS = 12
SLOW_EMA_BARS = 96
MOMENTUM_BARS = 60
MOMENTUM_MIN_BPS = 40        # 60-bar return needed to enter
TRAILING_STOP_BPS = 250      # sell when close is this far below the peak
REENTRY_COOLDOWN_BARS = 30   # bars to wait after an exit before re-entering
LOSS_CAP_QUOTE_UNITS = 35_000_000  # $35 below the $1,000 start: stop trading
BUY_MAX_SLIPPAGE_BPS = 100
SELL_MAX_SLIPPAGE_BPS = 200
BPS = 10_000


class TrendBot:
    """State for one run. All state derives from the bars and fills seen."""

    def __init__(self, state):
        self.state = state
        self.start_equity = state.equity
        self.closes = []          # closes, oldest first, ints (price units)
        self.ema_fast = None
        self.ema_slow = None
        self.peak_close = 0       # highest close since the current entry
        self.last_exit_seq = -10 ** 9
        self.blocked = False      # set once the daily loss cap trips

    # -- indicators ----------------------------------------------------------
    def _update_indicators(self, close):
        self.closes.append(close)
        alpha_fast = 2.0 / (FAST_EMA_BARS + 1)
        alpha_slow = 2.0 / (SLOW_EMA_BARS + 1)
        if self.ema_fast is None:
            self.ema_fast = float(close)
            self.ema_slow = float(close)
        else:
            self.ema_fast += alpha_fast * (close - self.ema_fast)
            self.ema_slow += alpha_slow * (close - self.ema_slow)

    def _momentum_bps(self):
        """Return over the last MOMENTUM_BARS bars, in bps, or None."""
        if len(self.closes) <= MOMENTUM_BARS:
            return None
        old = self.closes[-1 - MOMENTUM_BARS]
        return (self.closes[-1] - old) * BPS // old

    # -- fills ---------------------------------------------------------------
    def _absorb_fills(self, batch):
        for fill in batch.get("fills", []):
            if fill.get("status") != "filled":
                continue
            if fill.get("symbol") != SYMBOL:
                continue
            if fill.get("side") == "buy":
                # A new entry resets the trailing-stop peak to its fill
                # price: a peak carried over from an earlier trade would
                # sit above the new entry and stop it out at once.
                self.peak_close = int(fill["price"])
            elif fill.get("side") == "sell":
                self.last_exit_seq = batch["seq"]

    # -- decisions -----------------------------------------------------------
    def on_batch(self, state, batch):
        if state.warming_up:
            return []
        bar = state.latest.get(SYMBOL)
        if bar is None:
            return []
        close = int(bar["c"])
        self._update_indicators(close)
        self._absorb_fills(batch)

        holding = SYMBOL in state.positions and state.positions[SYMBOL].qty > 0
        if holding and close > self.peak_close:
            self.peak_close = close

        # Daily loss cap: equity $35 under the start ends trading for the day.
        if not self.blocked and state.equity <= self.start_equity - LOSS_CAP_QUOTE_UNITS:
            self.blocked = True
        if self.blocked:
            if holding:
                return [self._sell_all(state)]
            return []

        if holding:
            if self.peak_close and close <= self.peak_close * (BPS - TRAILING_STOP_BPS) // BPS:
                return [self._sell_all(state)]
            return []

        # Flat: enter only on a confirmed uptrend, after any cooldown.
        if state.cash < 1_000_000:  # below the $1 minimum notional: cannot buy
            return []
        if state.seq - self.last_exit_seq < REENTRY_COOLDOWN_BARS:
            return []
        if self.ema_fast is None or self.ema_fast <= self.ema_slow:
            return []
        momentum = self._momentum_bps()
        if momentum is None or momentum < MOMENTUM_MIN_BPS:
            return []
        return [{
            "side": "buy",
            "symbol": SYMBOL,
            "notional_quote_units": state.cash,
            "max_slippage_bps": BUY_MAX_SLIPPAGE_BPS,
        }]

    def _sell_all(self, state):
        holding = state.positions[SYMBOL]
        return {
            "side": "sell",
            "symbol": SYMBOL,
            "qty": holding.qty,
            "max_slippage_bps": SELL_MAX_SLIPPAGE_BPS,
        }


def on_batch(state, batch):
    return _BOT.on_batch(state, batch)


def on_hello(state):
    global _BOT
    _BOT = TrendBot(state)


_BOT = None
makefun_bars.run(on_batch, on_hello=on_hello)
