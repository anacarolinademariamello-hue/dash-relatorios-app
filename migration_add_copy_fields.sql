-- ============================================================
-- Migração: adiciona campos de copy ao clients
-- Execute no SQL Editor do Supabase:
-- https://supabase.com/dashboard/project/eintkwxkzlxwqorxivnz/sql/new
-- ============================================================

ALTER TABLE clients
  ADD COLUMN IF NOT EXISTS tone_of_voice TEXT DEFAULT '',
  ADD COLUMN IF NOT EXISTS competitors   TEXT DEFAULT '';
