-- ============================================================
-- Migração: adiciona campos de metas e observações ao clients
-- Execute no SQL Editor do Supabase:
-- https://supabase.com/dashboard/project/eintkwxkzlxwqorxivnz/sql/new
-- ============================================================

ALTER TABLE clients
  ADD COLUMN IF NOT EXISTS goals        JSONB DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS observations TEXT  DEFAULT '';
