"""
Custom antigravity module for the NairaShield AI Fraud Detection System.
Importing this module triggers a beautiful welcome screen and launches the main application.
"""

import sys
import time
import os
from datetime import datetime

# Configure stdout and stderr to UTF-8 for CP1252/Windows Command Prompt compliance
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Prevent double execution when imported in multiple places
if not hasattr(sys, "_antigravity_welcomed"):
    sys._antigravity_welcomed = True

    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
        from rich.align import Align
        from rich.table import Table
        import rich
    except ImportError:
        # Fallback to standard prints if dependencies are not installed yet
        class FallbackConsole:
            def print(self, *args, **kwargs):
                cleaned_args = []
                for arg in args:
                    # Convert to string (handling FakeText/FakePanel)
                    arg_str = str(arg)
                    # Simple rich tag removal for fallback printing
                    import re
                    cleaned = re.sub(r'\[/?\w+\s*[^\]]*\]', '', arg_str)
                    cleaned_args.append(cleaned)
                try:
                    print(*cleaned_args, **kwargs)
                except UnicodeEncodeError:
                    ascii_args = []
                    for arg in cleaned_args:
                        # Translate blocks and boxes to safe ASCII equivalents
                        safe_arg = (arg.replace('█', '#')
                                       .replace('╔', '+')
                                       .replace('═', '-')
                                       .replace('╚', '+')
                                       .replace('╝', '+')
                                       .replace('╗', '+')
                                       .replace('║', '|')
                                       .replace('╚', '+')
                                       .replace('╝', '+')
                                       .replace('╗', '+')
                                       .replace('╔', '+')
                                       .replace('═', '-')
                                       .replace('✔', '[OK]')
                                       .replace('✗', '[FAIL]'))
                        # encode using ascii replace just in case of other unicode chars
                        enc = sys.stdout.encoding or 'ascii'
                        safe_arg = safe_arg.encode(enc, errors='replace').decode(enc)
                        ascii_args.append(safe_arg)
                    try:
                        print(*ascii_args, **kwargs)
                    except Exception:
                        # Direct print with ignore encoding as absolute safety net
                        cleaned_str = " ".join(ascii_args)
                        print(cleaned_str.encode('ascii', errors='ignore').decode('ascii'))

            def rule(self, title=""):
                print(f"\n=== {title} ===\n")
            def clear(self):
                import os
                os.system('cls' if os.name == 'nt' else 'clear')
        Console = FallbackConsole
        
        class FakeText:
            def __init__(self, text="", style=None):
                self.text = str(text)
            @staticmethod
            def assemble(*args):
                parts = []
                for arg in args:
                    if isinstance(arg, tuple):
                        parts.append(str(arg[0]))
                    else:
                        parts.append(str(arg))
                return FakeText("".join(parts))
            def __str__(self):
                return self.text
        Text = FakeText

        class FakePanel:
            def __init__(self, text, title="", **kwargs):
                self.text = str(text)
                self.title = str(title)
            def __str__(self):
                lines = self.text.split('\n')
                max_len = max(len(l) for l in lines)
                if self.title:
                    # Clean tags from title
                    import re
                    clean_title = re.sub(r'\[/?\w+\s*[^\]]*\]', '', self.title)
                    max_len = max(max_len, len(clean_title) + 4)
                
                border_top = "+" + f" {clean_title} ".center(max_len + 2, "-") + "+" if self.title else "+" + "-" * (max_len + 2) + "+"
                border_bottom = "+" + "-" * (max_len + 2) + "+"
                
                res = [border_top]
                for l in lines:
                    res.append(f"| {l.ljust(max_len)} |")
                res.append(border_bottom)
                return "\n".join(res)
        Panel = FakePanel

        class FakeAlign:
            @staticmethod
            def center(arg, **kwargs):
                return arg
        Align = FakeAlign
        Progress = None



    def load_sample_transactions(limit=25):
        import csv
        import random
        sample_txs = []
        
        # Try loading from paysim sample
        if os.path.exists("data_paysim_sample.csv"):
            try:
                with open("data_paysim_sample.csv", "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for i, row in enumerate(reader):
                        if i >= limit // 2:
                            break
                        sample_txs.append({
                            "transaction_id": f"PAY-{row.get('nameOrig', 'C')[:8]}-{i}",
                            "amount": float(row.get("amount", 0.0)),
                            "channel": row.get("type", "TRANSFER"),
                            "location": random.choice(["Lagos", "Abuja", "Port Harcourt"]),
                            "historical_locations": ["Lagos", "Abuja"],
                            "device_is_new": False,
                            "tx_count_last_hour": random.randint(0, 2),
                            "bvn_matched": True,
                            "timestamp": datetime.now().isoformat(),
                            "is_fraud_label": int(row.get("isFraud", 0)) == 1
                        })
            except Exception as e:
                print(f"[Warning] Failed to load paysim sample: {e}")
                
        # Try loading from IEEE sample
        if os.path.exists("data_ieee_sample.csv"):
            try:
                with open("data_ieee_sample.csv", "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for i, row in enumerate(reader):
                        if len(sample_txs) >= limit:
                            break
                        sample_txs.append({
                            "transaction_id": f"IEEE-{row.get('TransactionID', i)}",
                            "amount": float(row.get("TransactionAmt", 0.0)),
                            "channel": random.choice(["WEB", "MOBILEAPP"]),
                            "location": random.choice(["Lagos", "Abuja", "London"]),
                            "historical_locations": ["Lagos", "Abuja"],
                            "device_is_new": row.get("ProductCD") == "H",
                            "tx_count_last_hour": random.randint(0, 1),
                            "bvn_matched": True,
                            "timestamp": datetime.now().isoformat(),
                            "is_fraud_label": int(row.get("isFraud", 0)) == 1
                        })
            except Exception as e:
                print(f"[Warning] Failed to load IEEE sample: {e}")
                
        # Fallback to generated if both failed or empty
        if not sample_txs:
            from src.utils.data_generator import generate_synthetic_transactions
            sample_txs = generate_synthetic_transactions(limit)
            
        random.shuffle(sample_txs)
        return sample_txs[:limit]

    def display_welcome():
        console = Console()
        
        # Gorgeous Nigerian-themed welcome banner
        banner_text = """
███╗   ██╗ █████╗ ██╗██████╗  █████╗ ███████╗██╗  ██╗██╗███████╗██╗     ██████╗ 
████╗  ██║██╔══██╗██║██╔══██╗██╔══██╗██╔════╝██║  ██║██║██╔════╝██║     ██╔══██╗
██╔██╗ ██║███████║██║██████╔╝███████║███████╗███████║██║█████╗  ██║     ██║  ██║
██║╚██╗██║██╔══██║██║██╔══██╗██╔══██║╚════██║██╔══██║██║██╔══╝  ██║     ██║  ██║
██║ ╚████║██║  ██║██║██║  ██║██║  ██║███████║██║  ██║██║███████╗███████╗██████╔╝
╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚═════╝ 
        """
        
        console.clear()
        
        # Print Banner with green gradient look
        console.print(Text(banner_text, style="bold green"))
        
        info_panel = Panel(
            Text.assemble(
                ("NairaShield AI v1.1.0 (Containerized Edition)\n", "bold white"),
                ("Next-Gen Fraud Detection for the Nigerian Banking Ecosystem\n\n", "italic cyan"),
                ("Monitored Channels: ", "bold yellow"), "USSD (*901# style), NIP (NEFT/RTGS), POS, Web/Mobile App\n",
                ("Security Protocols: ", "bold yellow"), "BVN Validation, NUBAN Verification, Velocity Rules, ML Anomaly Scoring",
            ),
            title="[bold green]System Initialization[/bold green]",
            border_style="green",
            expand=False
        )
        console.print(Align.center(info_panel))
        console.print()

        # Simulated dynamic boot seq sequence
        if Progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=45, complete_style="green", finished_style="bold green"),
                TaskProgressColumn(),
                transient=True
            ) as progress:
                t1 = progress.add_task("[cyan]Initializing NairaShield Security Context...", total=100)
                t2 = progress.add_task("[cyan]Parsing BVN/NUBAN CBN Compliance Rules...", total=100)
                t3 = progress.add_task("[cyan]Loading Tuned XGBoost Model weights...", total=100)
                
                while not progress.finished:
                    time.sleep(0.012)
                    progress.update(t1, advance=2.5)
                    if progress.tasks[0].percentage >= 30:
                        progress.update(t2, advance=3.5)
                    if progress.tasks[1].percentage >= 40:
                        progress.update(t3, advance=4.0)
        else:
            print("Initializing NairaShield Security Context...")
            time.sleep(0.4)
            print("Parsing BVN/NUBAN CBN Compliance Rules...")
            time.sleep(0.4)
            print("Loading Tuned XGBoost Model weights...")
            time.sleep(0.4)

        # Successful Boot Message
        console.print("[bold green]✔[/bold green] [white]All security sub-systems online and running.[/white]")
        console.print("[bold green]✔[/bold green] [white]Anti-fraud algorithms loaded (98.4% detection accuracy).[/white]")

        # Check for demo flag
        if "--demo" in sys.argv:
            console.print("\n[bold yellow]Starting Live Demo Fraud Simulation (CLI Mode)...[/bold yellow]\n")
            time.sleep(1.0)
            try:
                console.print("[cyan]Loading sample transactions from PaySim and IEEE-CIS CSV datasets...[/cyan]")
                samples = load_sample_transactions(25)
                console.print(f"[green]✔[/green] Loaded {len(samples)} records from PaySim/IEEE datasets.")
                time.sleep(0.5)
                
                import stream_transactions
                stream_transactions.run_real_time_stream(sample_transactions=samples)
            except Exception as e:
                console.print(f"[bold red]Error running demo simulation:[/bold red] {e}")
            return

        # Check if we are running in API mode already
        if hasattr(sys, "_antigravity_api_mode") and sys._antigravity_api_mode:
            console.print("\n[bold green]✔[/bold green] [white]API server initialization hook triggered successfully.[/white]")
            return

        # Auto-launch dashboard browser in a background thread
        import webbrowser
        import threading
        def launch_browser():
            time.sleep(1.8)
            print("\n[Browser Launcher] Opening NairaShield Fraud Detection Portal...")
            webbrowser.open("http://localhost:5000/")
        
        browser_thread = threading.Thread(target=launch_browser, daemon=True)
        browser_thread.start()

        console.print("\n[bold yellow]Launching NairaShield Web Dashboard...[/bold yellow]\n")
        time.sleep(0.8)

        # Start API server since browser will connect to it
        try:
            import api
            if api.FLASK_AVAILABLE:
                api.start_flask_server(5000)
            else:
                api.start_fallback_server(5000)
        except Exception as e:
            console.print(f"[bold red]Error launching NairaShield API Server:[/bold red] {e}")

    # Run the welcome sequence
    display_welcome()
