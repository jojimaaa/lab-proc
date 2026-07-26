"""Tradutor embarcado de LIBRAS — implementação de referência do documento
de arquitetura (PCS3724 — Sistemas Embarcados, Escola Politécnica da USP).

Pipeline de dutos e filtros: captura → pré-processamento → extração de
landmarks → classificação → lógica temporal → servidor de aplicação
(frontend web + síntese de voz), com um módulo transversal de monitoramento
de desempenho do processador.
"""

__version__ = "1.0.0"
