# Benchmark JARVIS

Ambiente misurato il 2026-10-11:

- OS: Windows 11 Home
- CPU: Intel Core i7-13700H (14 core / 20 thread)
- RAM: ~15,6 GB (al momento della misura poca RAM libera)
- GPU: Intel Iris Xe (nessuna NVIDIA → inferenza Ollama su CPU)
- Runtime: Ollama 0.40.0
- Modello: `llama3.2:3b` Q4_K_M (~2,0 GB)
- Prompt: `Rispondi in una sola frase: che ore sono tipicamente a mezzogiorno?`
- Opzioni: `num_ctx=2048`, `num_predict=64`, `temperature=0.2`
- Prove: 1 a freddo + 3 a caldo

## Iniziale (prima delle ottimizzazioni applicative)

| Metrica | Valore |
| --- | --- |
| Cold load | 8,54 s |
| Cold TTFT | 9,23 s |
| Cold totale | 11,46 s |
| Cold tok/s | 14,73 |
| Warm TTFT medio | 0,185 s |
| Warm totale medio | 2,82 s |
| Warm tok/s medio | 15,35 |

## Dopo ottimizzazioni codice (stesso modello)

| Metrica | Valore |
| --- | --- |
| Warm TTFT medio | 0,298 s |
| Warm totale medio | 2,57 s |
| Warm tok/s medio | 16,07 |
| Strumento diretto `stato sistema` | ~272 ms |
| Risposta generativa breve via `/chat` | ~12 s (variabile su CPU/RAM) |
| Streaming TTFT (prova live) | ~0,5 s a modello caldo |

Confronto: la velocità di generazione resta ~15–16 tok/s (limite CPU, non del solo codice). Il guadagno applicativo è evitare del tutto l’inferenza sui comandi diretti e ridurre contesto/`num_predict`.
