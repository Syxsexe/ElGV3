#!/usr/bin/env python3
"""
run_mock_dian.py — Arranca el servidor mock de DIAN para pruebas locales.

Uso:
    python backend/run_mock_dian.py          # Puerto 8081 por defecto
    python backend/run_mock_dian.py --port 9090
    python backend/run_mock_dian.py --reject   # Fuerza rechazo
    python backend/run_mock_dian.py --contingency  # Simula contingencia
"""
import argparse
import sys
import os

# Ensure backend is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.dian.mock_server import app, FORCE_REJECT, FORCE_CONTINGENCY, SIMULATE_DELAY

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock DIAN Server para pruebas")
    parser.add_argument("--port", type=int, default=8081, help="Puerto (default: 8081)")
    parser.add_argument("--reject", action="store_true", help="Forzar rechazo de facturas")
    parser.add_argument("--contingency", action="store_true", help="Simular contingencia")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay simulado en segundos")
    args = parser.parse_args()

    if args.reject:
        import app.dian.mock_server as ms
        ms.FORCE_REJECT = True
    if args.contingency:
        import app.dian.mock_server as ms
        ms.FORCE_CONTINGENCY = True
    if args.delay:
        import app.dian.mock_server as ms
        ms.SIMULATE_DELAY = args.delay

    import uvicorn

    print("╔══════════════════════════════════════════════╗")
    print("║      MOCK DIAN — Servicio de Pruebas        ║")
    print("╠══════════════════════════════════════════════╣")
    print(f"║  Puerto:   {args.port:<39}║")
    print(f"║  Rechazar: {str(args.reject):<39}║")
    print(f"║  Conting.: {str(args.contingency):<39}║")
    print(f"║  Delay:    {args.delay}s{' ' * 34}║")
    print("╠══════════════════════════════════════════════╣")
    print("║  Endpoint: /WcfDianCustomerServices.svc     ║")
    print("║  Health:   /health                          ║")
    print("║  Config:   POST /admin/config               ║")
    print("╚══════════════════════════════════════════════╝")

    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")
