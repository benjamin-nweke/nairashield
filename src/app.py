"""
Main App entry point for NairaShield AI Fraud Detection.
Contains the interactive CLI loop.
"""

import sys
from datetime import datetime
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.prompt import Prompt, IntPrompt
    from rich.align import Align
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    
    class FallbackConsole:
        def print(self, *args, **kwargs):
            cleaned_args = []
            for arg in args:
                arg_str = str(arg)
                import re
                cleaned = re.sub(r'\[/?\w+\s*[^\]]*\]', '', arg_str)
                cleaned_args.append(cleaned)
            try:
                print(*cleaned_args, **kwargs)
            except UnicodeEncodeError:
                ascii_args = []
                for arg in cleaned_args:
                    safe_arg = (arg.replace('✔', '[OK]')
                                   .replace('✗', '[FAIL]')
                                   .replace('₦', 'NGN'))
                    ascii_args.append(safe_arg)
                print(*ascii_args, **kwargs)

        def rule(self, title=""):
            import re
            cleaned = re.sub(r'\[/?\w+\s*[^\]]*\]', '', title)
            print(f"\n{'=' * 20} {cleaned} {'=' * 20}\n")

        def status(self, title=""):
            class DummyStatus:
                def __enter__(self):
                    import re
                    cleaned = re.sub(r'\[/?\w+\s*[^\]]*\]', '', title)
                    print(f"... {cleaned}")
                    return self
                def __exit__(self, exc_type, exc_val, exc_tb):
                    pass
            return DummyStatus()

    Console = FallbackConsole

    class FallbackTable:
        def __init__(self, title="", **kwargs):
            self.title = title
            self.columns = []
            self.rows = []

        def add_column(self, header, **kwargs):
            self.columns.append(str(header))

        def add_row(self, *args):
            self.rows.append([str(a) for a in args])

        def __str__(self):
            import re
            clean_title = re.sub(r'\[/?\w+\s*[^\]]*\]', '', self.title)
            res = []
            if clean_title:
                res.append(f"\n--- {clean_title} ---")
            if not self.columns:
                return ""
            
            widths = [len(re.sub(r'\[/?\w+\s*[^\]]*\]', '', col)) for col in self.columns]
            for row in self.rows:
                for i, cell in enumerate(row):
                    cell_clean = re.sub(r'\[/?\w+\s*[^\]]*\]', '', cell)
                    if i < len(widths):
                        widths[i] = max(widths[i], len(cell_clean))
            
            border = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
            
            header_cells = []
            for col, w in zip(self.columns, widths):
                col_clean = re.sub(r'\[/?\w+\s*[^\]]*\]', '', col)
                header_cells.append(f" {col_clean.ljust(w)} ")
            res.append(border)
            res.append("|" + "|".join(header_cells) + "|")
            res.append(border)
            
            for row in self.rows:
                row_cells = []
                for i, cell in enumerate(row):
                    cell_clean = re.sub(r'\[/?\w+\s*[^\]]*\]', '', cell)
                    w = widths[i] if i < len(widths) else len(cell_clean)
                    row_cells.append(f" {cell_clean.ljust(w)} ")
                res.append("|" + "|".join(row_cells) + "|")
            res.append(border)
            return "\n".join(res)

    Table = FallbackTable

    class FallbackPanel:
        def __init__(self, content, title="", **kwargs):
            self.content = content
            self.title = title

        def __str__(self):
            import re
            clean_title = re.sub(r'\[/?\w+\s*[^\]]*\]', '', self.title)
            lines = str(self.content).split('\n')
            max_len = max(len(re.sub(r'\[/?\w+\s*[^\]]*\]', '', l)) for l in lines)
            if clean_title:
                max_len = max(max_len, len(clean_title) + 4)
            
            border_top = "+" + f" {clean_title} ".center(max_len + 2, "-") + "+" if clean_title else "+" + "-" * (max_len + 2) + "+"
            border_bottom = "+" + "-" * (max_len + 2) + "+"
            
            res = [border_top]
            for l in lines:
                l_clean = re.sub(r'\[/?\w+\s*[^\]]*\]', '', l)
                res.append(f"| {l_clean.ljust(max_len)} |")
            res.append(border_bottom)
            return "\n".join(res)

    Panel = FallbackPanel

    class FallbackPrompt:
        @staticmethod
        def ask(prompt_text, choices=None, default=None):
            import re
            clean_prompt = re.sub(r'\[/?\w+\s*[^\]]*\]', '', prompt_text)
            choice_str = f" ({'/'.join(choices)})" if choices else ""
            default_str = f" [default: {default}]" if default is not None else ""
            val = input(f"{clean_prompt}{choice_str}{default_str}: ").strip()
            if not val and default is not None:
                return default
            if choices and val not in choices:
                print(f"Invalid choice. Choose from {choices}")
                return FallbackPrompt.ask(prompt_text, choices, default)
            return val

    Prompt = FallbackPrompt

    class FallbackIntPrompt:
        @staticmethod
        def ask(prompt_text, default=None):
            import re
            clean_prompt = re.sub(r'\[/?\w+\s*[^\]]*\]', '', prompt_text)
            default_str = f" [default: {default}]" if default is not None else ""
            val = input(f"{clean_prompt}{default_str}: ").strip()
            if not val and default is not None:
                return default
            try:
                return int(val)
            except ValueError:
                print("Please enter a valid integer.")
                return FallbackIntPrompt.ask(prompt_text, default)

    IntPrompt = FallbackIntPrompt

    class FallbackAlign:
        @staticmethod
        def center(arg, **kwargs):
            return arg

    Align = FallbackAlign

    class DummyBox:
        def __getattr__(self, name):
            return None
    box = DummyBox()


from config.settings import WEIGHTS
from src.rules.engine import RuleEngine
from src.models.anomaly_detector import AnomalyDetector
from src.utils.nuban import validate_nuban, validate_bvn, NIGERIAN_BANKS
from src.utils.data_generator import generate_synthetic_transactions

console = Console()
rule_engine = RuleEngine()
model = AnomalyDetector()

# Generate and train on initial data set
initial_data = generate_synthetic_transactions(500)
model.train(initial_data)

def display_menu():
    table = Table(title="[bold green]NairaShield Dashboard Panel[/bold green]", box=box.ROUNDED, border_style="green")
    table.add_column("Option", style="cyan", justify="center")
    table.add_column("Security Task", style="white")
    table.add_column("Description", style="dim white")
    
    table.add_row("1", "Evaluate Single Transaction", "Verify and score a transfer in real-time")
    table.add_row("2", "Run Batch Fraud Simulation", "Simulate 200 transfers, train ML model, and show logs")
    table.add_row("3", "NUBAN & BVN Integrity Check", "Verify account format against CBN standards")
    table.add_row("4", "Inspect Risk Weights", "Display config risk variables and limits")
    table.add_row("5", "System Exit", "Shutdown security console")
    
    console.print(Align.center(table))

def run_single_evaluation():
    console.rule("[bold cyan]Real-time Transaction Evaluation[/bold cyan]")
    
    # Inputs
    amount = float(Prompt.ask("Enter Transaction Amount (NGN)", default="25000"))
    channel = Prompt.ask("Enter Transaction Channel", choices=["USSD", "WEB", "MOBILEAPP", "POS", "ATM"], default="MOBILEAPP")
    location = Prompt.ask("Enter Current Location", default="Lagos")
    bvn_matched = Prompt.ask("Does BVN name match Account registration? (y/n)", choices=["y", "n"], default="y") == "y"
    tx_count_last_hour = IntPrompt.ask("Transactions in last 60 minutes", default=1)
    
    # Process
    tx = {
        "amount": amount,
        "channel": channel,
        "location": location,
        "historical_locations": ["Lagos", "Abuja"],
        "device_is_new": amount > 100000.0,  # Simulate device status
        "tx_count_last_hour": tx_count_last_hour,
        "bvn_matched": bvn_matched,
        "timestamp": datetime.now().isoformat()
    }
    
    rule_res = rule_engine.evaluate(tx)
    ml_res = model.predict_anomaly_score(tx)
    
    # Risk aggregation logic
    overall_score = max(rule_res["rule_risk_score"], ml_res)
    decision = rule_res["rule_decision"]
    if overall_score >= 0.8:
        decision = "BLOCKED"
    elif overall_score >= 0.5 and decision != "BLOCKED":
        decision = "PENDING_OTP"
    
    # Color decision
    color = "green"
    if decision == "BLOCKED":
        color = "bold red"
    elif decision == "PENDING_OTP":
        color = "bold yellow"
        
    # Result Panel
    res_table = Table(box=box.SIMPLE)
    res_table.add_column("Metric", style="cyan")
    res_table.add_column("Result Details", style="white")
    
    res_table.add_row("Rule Risk Score", f"{rule_res['rule_risk_score'] * 100:.1f}%")
    res_table.add_row("Triggered Rules", ", ".join(rule_res["triggered_rules"]) if rule_res["triggered_rules"] else "None (Clear)")
    res_table.add_row("AI Anomaly Score", f"{ml_res * 100:.1f}%")
    res_table.add_row("Overall Risk Index", f"{overall_score * 100:.1f}%")
    res_table.add_row("Final Action Decision", f"[{color}]{decision}[/{color}]")
    
    console.print(Panel(res_table, title="[bold green]Security Decision Report[/bold green]", border_style=color))
    Prompt.ask("\nPress Enter to return to Dashboard...")

def run_batch_simulation():
    console.rule("[bold cyan]System Batch Simulation & Machine Learning Evaluation[/bold cyan]")
    
    with console.status("[yellow]Generating synthetic bank transactions (NairaShield dataset)...[/yellow]"):
        sim_data = generate_synthetic_transactions(200)
    
    console.print(f"[green]✔[/green] Generated 200 mock transactions.")
    
    with console.status("[yellow]Training Isolation Forest anomaly models...[/yellow]"):
        model.train(sim_data)
    
    console.print(f"[green]✔[/green] Model retrained successfully.")
    
    blocked = 0
    otp = 0
    approved = 0
    fraud_detected = 0
    false_positives = 0
    
    table = Table(title="Simulation Run Log (Sample)", box=box.MINIMAL, border_style="cyan")
    table.add_column("Tx ID", style="dim")
    table.add_column("Amount", justify="right")
    table.add_column("Channel", style="yellow")
    table.add_column("Location", style="cyan")
    table.add_column("AI Anomaly", justify="right")
    table.add_column("Decision", justify="center")
    
    sample_printed = 0
    for tx in sim_data:
        rule_res = rule_engine.evaluate(tx)
        ml_score = model.predict_anomaly_score(tx)
        
        overall = max(rule_res["rule_risk_score"], ml_score)
        
        decision = "APPROVED"
        if overall >= 0.8:
            decision = "BLOCKED"
            blocked += 1
        elif overall >= 0.5:
            decision = "PENDING_OTP"
            otp += 1
        else:
            approved += 1
            
        is_labeled_fraud = tx.get("is_fraud_label", False)
        if decision in ["BLOCKED", "PENDING_OTP"]:
            if is_labeled_fraud:
                fraud_detected += 1
            else:
                false_positives += 1
                
        # Print a sample of 8 to console
        if sample_printed < 8 and is_labeled_fraud:
            color = "red" if decision == "BLOCKED" else "yellow" if decision == "PENDING_OTP" else "green"
            table.add_row(
                tx["transaction_id"],
                f"₦{tx['amount']:,}",
                tx["channel"],
                tx["location"],
                f"{ml_score * 100:.0f}%",
                f"[{color}]{decision}[/{color}]"
            )
            sample_printed += 1

    console.print(table)
    
    # Summary Card
    summary_table = Table(box=box.SIMPLE, title="Simulation Summary metrics")
    summary_table.add_column("Action", style="cyan")
    summary_table.add_column("Count", justify="right")
    summary_table.add_column("Percentage", justify="right")
    
    total = len(sim_data)
    summary_table.add_row("Approved", str(approved), f"{approved/total * 100:.1f}%")
    summary_table.add_row("Pending OTP", str(otp), f"{otp/total * 100:.1f}%")
    summary_table.add_row("Blocked", str(blocked), f"{blocked/total * 100:.1f}%")
    
    console.print(Panel(summary_table, title="[green]System Security Output[/green]"))
    Prompt.ask("\nPress Enter to return to Dashboard...")

def run_integrity_check():
    console.rule("[bold cyan]CBN NUBAN & BVN Integrity Check[/bold cyan]")
    
    # Display supported banks
    bank_table = Table(title="Registered Banks (CBN Codes)", box=box.ROUNDED, border_style="cyan")
    bank_table.add_column("Code", style="yellow")
    bank_table.add_column("Bank Name", style="white")
    for code, name in list(NIGERIAN_BANKS.items())[:6]:  # Show first 6 for neatness
        bank_table.add_row(code, name)
    console.print(bank_table)
    
    bvn = Prompt.ask("Enter Bank Verification Number (BVN) to validate", default="22233344455")
    if validate_bvn(bvn):
        console.print("[green]✔ BVN Format Validated.[/green] (11-digits compliance)")
    else:
        console.print("[red]✗ BVN Check Failed. Must be exactly 11 digits.[/red]")
        
    bank_code = Prompt.ask("Enter 3-Digit Bank Code", default="058")
    nuban = Prompt.ask("Enter 10-Digit Account Number (NUBAN) to check", default="0123456789")
    
    if validate_nuban(nuban, bank_code):
        bank_name = NIGERIAN_BANKS.get(bank_code, "Unknown Bank")
        console.print(f"[green]✔ NUBAN Signature Valid for {bank_name}![/green]")
    else:
        console.print(f"[red]✗ NUBAN Validation Failed for Bank Code {bank_code}.[/red]")
        
    Prompt.ask("\nPress Enter to return to Dashboard...")

def run_risk_weights():
    console.rule("[bold cyan]System Risk Parameter Specifications[/bold cyan]")
    
    table = Table(box=box.ROUNDED, border_style="yellow")
    table.add_column("Threat Identifier", style="cyan")
    table.add_column("Config Weight Level (0.0 to 1.0)", justify="right")
    table.add_column("Criticality Status", style="magenta")
    
    for key, weight in WEIGHTS.items():
        status = "CRITICAL" if weight >= 0.8 else "HIGH" if weight >= 0.6 else "MEDIUM"
        table.add_row(key, f"{weight:.2f}", status)
        
    console.print(table)
    Prompt.ask("\nPress Enter to return to Dashboard...")

def main():
    while True:
        try:
            display_menu()
            choice = Prompt.ask("Choose Security Task [1-5]", choices=["1", "2", "3", "4", "5"], default="1")
            
            if choice == "1":
                run_single_evaluation()
            elif choice == "2":
                run_batch_simulation()
            elif choice == "3":
                run_integrity_check()
            elif choice == "4":
                run_risk_weights()
            elif choice == "5":
                console.print("[bold green]NairaShield Security System shutdown. Goodbye.[/bold green]")
                break
        except KeyboardInterrupt:
            console.print("\n[bold red]Interrupted. Shutdown complete.[/bold red]")
            break

if __name__ == "__main__":
    main()
