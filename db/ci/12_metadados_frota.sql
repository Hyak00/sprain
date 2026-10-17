-- Datas antigas desconhecidas permanecem NULL; nao apresentar migracao como atualizacao do cadastro.
ALTER TABLE veiculos ADD COLUMN IF NOT EXISTS atualizado_em TIMESTAMPTZ;
