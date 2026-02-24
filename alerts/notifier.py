"""
알림 시스템: Slack / Telegram 발송
- 매수 추천, 매도 경고, 방어 모드 알림
"""
import os
import json
from datetime import datetime
from typing import Optional

import requests


class Notifier:
    """Slack/Telegram 알림 발송"""

    def __init__(self, config: dict):
        self.slack_enabled = config.get("slack", {}).get("enabled", False)
        self.slack_webhook = os.environ.get(
            "SLACK_WEBHOOK_URL",
            config.get("slack", {}).get("webhook_url", ""),
        )

        self.telegram_enabled = config.get("telegram", {}).get("enabled", False)
        self.telegram_token = os.environ.get(
            "TELEGRAM_BOT_TOKEN",
            config.get("telegram", {}).get("bot_token", ""),
        )
        self.telegram_chat_id = os.environ.get(
            "TELEGRAM_CHAT_ID",
            config.get("telegram", {}).get("chat_id", ""),
        )

    # -------------------------------------------------------
    # 메시지 포맷
    # -------------------------------------------------------

    def format_report(self, report: dict) -> str:
        """최종 리포트를 알림 메시지로 포맷"""
        picks = report.get("final_picks", [])
        if not picks:
            return "No picks today."

        lines = [
            f"*AI Stock Engine Report*",
            f"_{datetime.now().strftime('%Y-%m-%d %H:%M')}_",
            "",
        ]

        # 매수 추천
        buys = [p for p in picks if p["signal"] in ("STRONG_BUY", "BUY")]
        if buys:
            lines.append("*Buy Signals:*")
            for p in buys:
                emoji = "🟢" if p["signal"] == "STRONG_BUY" else "🔵"
                lines.append(
                    f"  {emoji} *{p['ticker']}* — Score {p['total_score']:.2f} "
                    f"(Q:{p['quant_score']:.2f} M:{p['macro_score']:.2f} N:{p['nlp_score']:.2f})"
                )
            lines.append("")

        # 매도/경고
        sells = [p for p in picks if p["signal"] in ("SELL", "AVOID")]
        if sells:
            lines.append("*Sell/Avoid:*")
            for p in sells:
                emoji = "🔴" if p["signal"] == "AVOID" else "🟠"
                lines.append(f"  {emoji} *{p['ticker']}* — {p['signal']} ({p['total_score']:.2f})")
            lines.append("")

        # 매크로
        macro = report.get("engine2", {})
        if macro.get("defense_mode"):
            lines.append(f"⚠️ *Defense Mode Active* (Risk: {macro.get('risk_score', 'N/A')})")
            for reason in macro.get("defense_reasons", []):
                lines.append(f"  - {reason}")

        return "\n".join(lines)

    def format_surge_alert(self, surge_list: list[dict]) -> str:
        """거래대금 폭증 긴급 알림"""
        if not surge_list:
            return ""

        lines = ["🚨 *Volume Surge Alert*", ""]
        for s in surge_list[:10]:
            lines.append(
                f"  *{s['ticker']}* — {s['ratio_5d']}x (5d avg), "
                f"Market Cap: ${s.get('market_cap_b', '?')}B"
            )

        return "\n".join(lines)

    def format_defense_alert(self, risk_result: dict, allocation: dict) -> str:
        """방어 모드 전환 알림"""
        lines = [
            "🛡️ *Defense Mode Activated*",
            f"Risk Score: {risk_result['risk_score']:.2f}",
            "",
        ]

        for reason in risk_result.get("defense_reasons", []):
            lines.append(f"  - {reason}")

        lines.append("")
        lines.append(f"Defense Ratio: {allocation.get('defense_ratio', 0):.0%}")

        for sector, data in allocation.get("sectors", {}).items():
            tickers = [t["ticker"] for t in data.get("tickers", [])[:3]]
            lines.append(f"  {sector}: {', '.join(tickers)} ({data['weight']:.0%})")

        return "\n".join(lines)

    # -------------------------------------------------------
    # 발송
    # -------------------------------------------------------

    def send(self, message: str):
        """활성화된 채널로 메시지 발송"""
        if not message:
            return

        if self.slack_enabled:
            self._send_slack(message)
        if self.telegram_enabled:
            self._send_telegram(message)

        if not self.slack_enabled and not self.telegram_enabled:
            # 콘솔 출력 (fallback)
            print("\n[ALERT]")
            print(message)

    def _send_slack(self, message: str):
        """Slack Webhook으로 발송"""
        if not self.slack_webhook:
            print("[WARN] Slack webhook URL not configured")
            return

        try:
            resp = requests.post(
                self.slack_webhook,
                json={"text": message},
                timeout=10,
            )
            if resp.status_code != 200:
                print(f"[SLACK ERROR] {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"[SLACK ERROR] {e}")

    def _send_telegram(self, message: str):
        """Telegram Bot API로 발송"""
        if not self.telegram_token or not self.telegram_chat_id:
            print("[WARN] Telegram bot token/chat_id not configured")
            return

        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            resp = requests.post(
                url,
                json={
                    "chat_id": self.telegram_chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
            if resp.status_code != 200:
                print(f"[TELEGRAM ERROR] {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"[TELEGRAM ERROR] {e}")


if __name__ == "__main__":
    config = {
        "slack": {"enabled": False},
        "telegram": {"enabled": False},
    }

    notifier = Notifier(config)

    # 테스트: 콘솔 출력
    mock_report = {
        "final_picks": [
            {"ticker": "NVDA", "signal": "STRONG_BUY", "total_score": 0.85,
             "quant_score": 0.9, "macro_score": 0.7, "nlp_score": 0.88},
            {"ticker": "TSLA", "signal": "HOLD", "total_score": 0.45,
             "quant_score": 0.5, "macro_score": 0.7, "nlp_score": 0.3},
        ],
        "engine2": {"defense_mode": False, "risk_score": 0.3},
    }

    message = notifier.format_report(mock_report)
    notifier.send(message)
