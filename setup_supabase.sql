-- ============================================================
-- Dash Digital — Supabase Setup
-- Run this once in the Supabase SQL Editor:
-- https://supabase.com/dashboard/project/eintkwxkzlxwqorxivnz/sql/new
-- ============================================================

-- ── Clients table ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clients (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  key                  TEXT UNIQUE NOT NULL,          -- e.g. "dashdgt"
  name                 TEXT NOT NULL,                 -- e.g. "Dash Digital"
  handle               TEXT NOT NULL,                 -- e.g. "@dashdgt"
  instagram_id         TEXT NOT NULL,                 -- Instagram Business account ID
  facebook_account_id  TEXT NOT NULL,                 -- Meta Ads account ID (without "act_")
  bio                  TEXT DEFAULT '',
  tags                 TEXT[] DEFAULT '{}',
  avatar               TEXT DEFAULT '📊',
  footer               TEXT DEFAULT '',
  colors               JSONB DEFAULT '{
    "p": "#003f7c", "p2": "#1a5a9a", "a": "#f8b940", "ad": "#d99a20",
    "al": "rgba(248,185,64,0.13)", "pl": "rgba(0,63,124,0.08)",
    "bg": "#f0f3f8", "header_end": "#2471c8",
    "period_color": "#ffe08a", "stat_color": "#f8b940"
  }',
  active               BOOLEAN DEFAULT TRUE,
  created_at           TIMESTAMPTZ DEFAULT NOW(),
  updated_at           TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS clients_updated_at ON clients;
CREATE TRIGGER clients_updated_at
  BEFORE UPDATE ON clients
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── Report history table ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS report_history (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_key   TEXT NOT NULL REFERENCES clients(key) ON DELETE CASCADE,
  date_from    DATE NOT NULL,
  date_to      DATE NOT NULL,
  report_type  TEXT NOT NULL DEFAULT 'Geral',  -- "Geral" | "Só Orgânico" | "Só Pago"
  metrics      JSONB NOT NULL DEFAULT '{}',
  generated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookups by client + period
CREATE INDEX IF NOT EXISTS idx_report_history_lookup
  ON report_history (client_key, date_from, date_to, report_type);

CREATE INDEX IF NOT EXISTS idx_report_history_client
  ON report_history (client_key, generated_at DESC);

-- ── Row Level Security ────────────────────────────────────────────────────────
-- Using service_role key bypasses RLS, so these are for reference only.
-- Disable RLS if you only use service_role (recommended for private tools):
ALTER TABLE clients       DISABLE ROW LEVEL SECURITY;
ALTER TABLE report_history DISABLE ROW LEVEL SECURITY;

-- ── Seed existing clients ─────────────────────────────────────────────────────
-- Copy your 4 existing profiles from profiles.py into Supabase.
-- Run each INSERT below to populate the clients table.

INSERT INTO clients (key, name, handle, instagram_id, facebook_account_id, bio, tags, avatar, footer, colors)
VALUES (
  'dashdgt',
  'Dash Digital',
  '@dashdgt',
  '17841465464445282',
  '3730768157200767',
  'Agência de marketing digital especializada em tráfego pago para professores que querem lançar e escalar cursos online.',
  ARRAY['#TráfegoPago','#LançamentoDeCursos','#MarketingDigital','#ProfessoresDigitais','#MetaAds'],
  '📊',
  'Relatório gerado para a <strong>Dash Digital</strong> por Dash Digital.',
  '{"p":"#003f7c","p2":"#1a5a9a","a":"#f8b940","ad":"#d99a20","al":"rgba(248,185,64,0.13)","pl":"rgba(0,63,124,0.08)","bg":"#f0f3f8","header_end":"#2471c8","period_color":"#ffe08a","stat_color":"#f8b940"}'
) ON CONFLICT (key) DO NOTHING;

INSERT INTO clients (key, name, handle, instagram_id, facebook_account_id, bio, tags, avatar, footer, colors)
VALUES (
  'questaodetexto',
  'Questão de Texto',
  '@questaodetexto',
  '17841466194254352',
  '2014012268996583',
  'Canal de conteúdo sobre língua portuguesa, redação e literatura — criando conexão com o aprendizado de forma leve e profunda.',
  ARRAY['#LínguaPortuguesa','#Redação','#Literatura','#ENEM','#Educação'],
  '📝',
  'Relatório gerado para o <strong>Questão de Texto</strong> por Dash Digital.',
  '{"p":"#323a92","p2":"#4a54c7","a":"#e960b2","ad":"#c940a0","al":"rgba(233,96,178,0.13)","pl":"rgba(50,58,146,0.08)","bg":"#f3f4fd","header_end":"#5c68d8","period_color":"#fbbe1b","stat_color":"#e960b2"}'
) ON CONFLICT (key) DO NOTHING;

INSERT INTO clients (key, name, handle, instagram_id, facebook_account_id, bio, tags, avatar, footer, colors)
VALUES (
  'wanzeller',
  'Prof. Wanzeller',
  '@prof.wanzeller',
  '17841479657213211',
  '1429787371828065',
  'Professor de matemática apaixonado por transformar alunos e criar professores de sucesso no digital.',
  ARRAY['#ProfessorDigital','#Matemática','#CursosOnline','#EAD','#Educação'],
  '🎓',
  'Relatório gerado para o professor <strong>Wanzeller</strong> por Dash Digital.',
  '{"p":"#0d2137","p2":"#1a3a5c","a":"#c9a227","ad":"#a88520","al":"rgba(201,162,39,0.13)","pl":"rgba(13,33,55,0.08)","bg":"#f0f2f5","header_end":"#1e4a70","period_color":"#fde68a","stat_color":"#c9a227"}'
) ON CONFLICT (key) DO NOTHING;

INSERT INTO clients (key, name, handle, instagram_id, facebook_account_id, bio, tags, avatar, footer, colors)
VALUES (
  'wanderson',
  'Prof. Wanderson Melo',
  '@professor_wandersonmelo',
  '17841410776971693',
  '372281334793918',
  'Professor de língua portuguesa para concursos de alto nível — magistratura, MP, DPU, AGU e Polícia Federal.',
  ARRAY['#Português','#ConcursoPublico','#Magistratura','#MinistérioPublico','#LinguaPortuguesa'],
  '📚',
  'Relatório gerado para o professor <strong>Wanderson</strong> por Dash Digital.',
  '{"p":"#2c3a45","p2":"#3e5263","a":"#e1a185","ad":"#c47d5e","al":"rgba(225,161,133,0.15)","pl":"rgba(44,58,69,0.08)","bg":"#f4f2f0","header_end":"#4a6278","period_color":"#f5d0bc","stat_color":"#e1a185"}'
) ON CONFLICT (key) DO NOTHING;

-- ============================================================
-- Done! Your tables are set up and existing clients are seeded.
-- ============================================================
