"""
VoiceForward Demo Simulator
Simulates a live call by injecting text through the VoiceForward API.
No real phone call needed.

Usage:
  python demo/simulator.py --scenario high_risk_hinglish
  python demo/simulator.py --scenario domestic_violence_child
  python demo/simulator.py --scenario conflicting_signals
  python demo/simulator.py --all
"""
import asyncio
import httpx
import argparse
import sys
import os

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API_URL = os.getenv("NEXT_PUBLIC_API_URL", "http://localhost:8000")

SCENARIOS = {
    "high_risk_hinglish": {
        "description": "Hinglish caller, code-switching, suicidal ideation — Scenario 1 from DEMO_SCRIPT.md",
        "priority": "P1",
        "expected_risk": "CRITICAL",
        "helpline_url": f"{API_URL}/operator/{{call_sid}}",
        "segments": [
            {
                "text": "Main bahut thaka hoon… I can't do this anymore",
                "language": "hi",
                "delay": 0
            },
            {
                "text": "I've decided… kuch karna chahta hoon jo sab khatam kar de",
                "language": "hi",
                "delay": 4,
                "ambient": None
            },
            {
                "text": "I've decided. Pura soch liya hai.",
                "language": "hi",
                "delay": 4,
                "ambient": None
            },
            {
                "text": "mere paas bahut kum waqt hai",
                "language": "hi",
                "delay": 3,
                "ambient": None
            }
        ]
    },
    "domestic_violence_child": {
        "description": "Calm caller, child crying in background, shelter needed — Scenario 2",
        "priority": "P2",
        "expected_risk": "HIGH",
        "segments": [
            {
                "text": "I need somewhere safe to stay tonight",
                "language": "en",
                "delay": 0,
                "ambient": "child_crying"
            },
            {
                "text": "My husband… he gets angry. My child is with me.",
                "language": "en",
                "delay": 4,
                "ambient": "child_crying"
            },
            {
                "text": "We are in Mumbai, near Dharavi. Can you help?",
                "language": "en",
                "delay": 4,
                "ambient": None
            },
            {
                "text": "I'm not safe here. Please help me find a shelter.",
                "language": "en",
                "delay": 3,
                "ambient": None
            }
        ]
    },
    "conflicting_signals": {
        "description": "Laughing but describing self-harm history — Scenario 3 (conflict demo)",
        "priority": "P2",
        "expected_risk": "HIGH (CONFLICT shown)",
        "segments": [
            {
                "text": "Ha ha, I'm fine, really. Everything is okay.",
                "language": "en",
                "delay": 0,
                "ambient": None
            },
            {
                "text": "I tried something last week but it's okay now.",
                "language": "en",
                "delay": 4,
                "ambient": None
            },
            {
                "text": "I just wanted to talk to someone",
                "language": "en",
                "delay": 4,
                "ambient": None
            },
            {
                "text": "I've decided I won't do it again. Probably.",
                "language": "en",
                "delay": 3,
                "ambient": None
            }
        ]
    }
}


async def check_backend():
    """Verify backend is running."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{API_URL}/health")
            if response.status_code == 200:
                print(f"✅ Backend running at {API_URL}")
                return True
    except Exception as e:
        print(f"❌ Backend not available at {API_URL}: {e}")
        print("   Start backend with: uvicorn api.main:app --reload --port 8000")
        return False


async def run_scenario(scenario_name: str, call_sid: str | None = None):
    """Run a demo scenario by injecting text segments into the API."""
    scenario = SCENARIOS.get(scenario_name)
    if not scenario:
        print(f"❌ Unknown scenario: {scenario_name}")
        print(f"   Available: {', '.join(SCENARIOS.keys())}")
        return

    if call_sid is None:
        call_sid = f"demo_{scenario_name}_{int(asyncio.get_event_loop().time())}"

    print(f"\n{'='*60}")
    print(f"🎬 SCENARIO: {scenario_name}")
    print(f"   {scenario['description']}")
    print(f"   Expected risk: {scenario['expected_risk']}")
    print(f"   Call SID: {call_sid}")
    print(f"{'='*60}\n")

    print(f"📺 Open HUD: http://localhost:3000/operator/{call_sid}")
    print(f"📊 Supervisor: http://localhost:3000/supervisor")
    print()
    input("   Press ENTER when HUD is open, then watch it update in real-time...")
    print()

    async with httpx.AsyncClient(timeout=10.0) as client:
        for i, segment in enumerate(scenario["segments"]):
            if segment.get("delay", 0) > 0:
                print(f"   ⏳ Waiting {segment['delay']}s...")
                await asyncio.sleep(segment["delay"])

            text = segment["text"]
            language = segment.get("language", "en")
            ambient = segment.get("ambient")

            print(f"   [{i+1}/{len(scenario['segments'])}] [{language.upper()}] {text}")

            try:
                response = await client.post(
                    f"{API_URL}/api/demo/inject",
                    json={
                        "call_sid": call_sid,
                        "text": text,
                        "language": language,
                        "confidence": 0.85,
                        "ambient_override": ambient
                    }
                )
                if response.status_code == 200:
                    print(f"         ✓ Injected → watch HUD update")
                else:
                    print(f"         ✗ Injection failed: {response.status_code} {response.text}")
            except Exception as e:
                print(f"         ✗ Request error: {e}")

    print()
    print(f"✅ Scenario '{scenario_name}' complete!")
    print(f"   Review: http://localhost:3000/operator/{call_sid}")
    print(f"   Replay: http://localhost:3000/supervisor/replay/{call_sid}")
    print()


async def main():
    parser = argparse.ArgumentParser(
        description="VoiceForward Demo Simulator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Scenarios:
  high_risk_hinglish      — Scenario 1: Hinglish caller, suicidal ideation, code-switching
  domestic_violence_child — Scenario 2: DV caller, child crying, shelter needed
  conflicting_signals     — Scenario 3: Laughing caller with past attempt history (conflict demo)
  
Examples:
  python demo/simulator.py --scenario high_risk_hinglish
  python demo/simulator.py --all
  python demo/simulator.py --scenario conflicting_signals --call-sid my_custom_id
        """
    )
    parser.add_argument(
        "--scenario",
        choices=list(SCENARIOS.keys()),
        default="high_risk_hinglish",
        help="Which scenario to run"
    )
    parser.add_argument("--all", action="store_true", help="Run all scenarios sequentially")
    parser.add_argument("--call-sid", help="Custom call SID (auto-generated if not provided)")
    parser.add_argument("--api-url", default=API_URL, help=f"Backend API URL (default: {API_URL})")
    args = parser.parse_args()

    global API_URL
    API_URL = args.api_url

    if not await check_backend():
        sys.exit(1)

    if args.all:
        for scenario_name in SCENARIOS.keys():
            await run_scenario(scenario_name)
            print("\n" + "─" * 60 + "\n")
    else:
        await run_scenario(args.scenario, args.call_sid)


if __name__ == "__main__":
    asyncio.run(main())
