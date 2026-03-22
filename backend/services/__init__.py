"""
services/ — application-level orchestration layer for Soyog AI.

Packages:
  analytics_service  — fire-and-forget AI usage logging to Firestore
  cache_service      — Firestore-backed per-user AI response cache
  ai_service         — unified AI call wrapper (cache + AI + analytics)
"""
