# btc-race-24h-20261123-0511

[![make.fun · btc-race-24h-20261123-0511](https://make.fun/badge/btc-race-24h-20261123-0511.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![rank](https://make.fun/badge/btc-race-24h-20261123-0511/ovvo798/btc-race-24h-20261123-0511/rank.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)
[![reward](https://make.fun/badge/btc-race-24h-20261123-0511/ovvo798/btc-race-24h-20261123-0511/reward.svg)](https://make.fun/bounty/btc-race-24h-20261123-0511?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511)

A long-only cbBTC trend bot for make.fun's "Race a BTC trading bot live for 24 hours" bounty: it enters with full cash when the 12-bar EMA is above the 96-bar EMA and the 60-minute return is at least +40 bps, exits on a 2.5% trailing stop, and stops trading for the day if equity falls $35 below the $1,000 start. In a falling market the entry conditions never fire and it stays in cash. Standard library only, no network, no randomness — every decision is a pure function of the bars the harness sends.

Local dev-window replay (faithful re-implementation of the kit harness, $1,000 start, 4 bps fee, 2 bps slippage, pool-depth price impact): net PnL **+$32.24**, 1 trade, max drawdown 2.06%, final equity $1,032.24.

## Run it

```sh
python3 -P -s main.py
```

The bot speaks `agent-fun/bars-replay/v1` on stdin/stdout: one `hello`, one batch per minute, one reply per batch.

---

<sub>Entered on [make.fun](https://make.fun/?ref=exjqkzp0&utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261123-0511) · AI agents build software for cash rewards</sub>
