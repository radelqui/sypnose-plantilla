-- Subconjunto del esquema real de ~/sypnose-f1/registry.db (leído el 15-sep-2026) para las pruebas en modo local.
PRAGMA foreign_keys = ON;
CREATE TABLE actor (id TEXT PRIMARY KEY, clase TEXT NOT NULL CHECK (clase IN ('humano','ia')), rol TEXT, modelo TEXT);
CREATE TABLE plan (
  id TEXT PRIMARY KEY,
  clase TEXT NOT NULL CHECK (clase IN ('investigar','migrar','mantener','retirar')),
  que TEXT NOT NULL, para TEXT NOT NULL, porque TEXT NOT NULL, afecta TEXT NOT NULL,
  estado TEXT NOT NULL DEFAULT 'propuesto' CHECK (estado IN ('propuesto','abierto','pausado','cerrado','rechazado')),
  autor TEXT NOT NULL, dueno TEXT, worktree TEXT UNIQUE,
  mejora TEXT, cuesta REAL, rompe TEXT, descartado TEXT, confianza TEXT, motivo_rechazo TEXT,
  abierto_en TEXT, cerrado_en TEXT, coste_real REAL DEFAULT 0,
  CHECK (estado!='abierto' OR (worktree IS NOT NULL AND dueno IS NOT NULL AND dueno LIKE 'H:%')),
  CHECK (dueno IS NULL OR dueno LIKE 'H:%'),
  CHECK (estado!='rechazado' OR motivo_rechazo IS NOT NULL)
);
CREATE TABLE requisito (
  plan_id TEXT NOT NULL REFERENCES plan(id) ON DELETE CASCADE, ref TEXT NOT NULL, ears TEXT NOT NULL,
  comprobacion TEXT NOT NULL CHECK (TRIM(comprobacion) <> ''), PRIMARY KEY (plan_id, ref)
);
CREATE TABLE tarea (
  id INTEGER PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES plan(id) ON DELETE CASCADE, req_ref TEXT NOT NULL, titulo TEXT NOT NULL,
  progreso TEXT NOT NULL DEFAULT 'pendiente' CHECK (progreso IN ('pendiente','bloqueada','trabajando','espera_firma','hecha','devuelta')),
  agente TEXT, coste REAL DEFAULT 0, bloqueada_por INTEGER REFERENCES tarea(id), verificada_por TEXT REFERENCES actor(id),
  FOREIGN KEY (plan_id, req_ref) REFERENCES requisito(plan_id, ref)
);
CREATE TABLE nodo (id TEXT PRIMARY KEY, tipo TEXT NOT NULL, nombre TEXT NOT NULL);
CREATE TABLE plan_objetivo (plan_id TEXT NOT NULL REFERENCES plan(id), nodo_id TEXT NOT NULL REFERENCES nodo(id), papel TEXT);
CREATE TABLE evento (id INTEGER PRIMARY KEY, cuando TEXT NOT NULL, actor TEXT NOT NULL, accion TEXT NOT NULL,
                     nodo_id TEXT, plan_id TEXT, detalle TEXT, firma TEXT);
CREATE TABLE evidencia (plan_id TEXT NOT NULL REFERENCES plan(id) ON DELETE CASCADE, nodo_id TEXT REFERENCES nodo(id),
                        fuente TEXT NOT NULL, dice TEXT NOT NULL, PRIMARY KEY (plan_id, fuente, dice));
CREATE TRIGGER evento_inmutable_d BEFORE DELETE ON evento BEGIN SELECT RAISE(ABORT,'evento es append-only'); END;
CREATE TRIGGER evento_inmutable_u BEFORE UPDATE ON evento BEGIN SELECT RAISE(ABORT,'evento es append-only'); END;
CREATE TRIGGER quien_ejecuta_no_juzga_u BEFORE UPDATE ON tarea WHEN NEW.progreso='espera_firma' AND (NEW.verificada_por IS NULL OR NEW.agente IS NULL OR NEW.verificada_por = NEW.agente) BEGIN SELECT RAISE(ABORT,'D7: quien ejecuta no juzga'); END;

INSERT INTO actor VALUES ('H:carlos', 'humano', 'dueno', NULL), ('IA:02-backend-api:claude-sonnet-5', 'ia', '02-backend-api', 'claude-sonnet-5');
INSERT INTO nodo VALUES ('proy:vmi3211028:rag-banking-agent', 'proyecto', 'rag-banking-agent');
INSERT INTO plan (id, clase, que, para, porque, afecta, estado, autor, dueno, worktree, abierto_en)
VALUES ('PLAN-CS-T01', 'mantener', '[coforge-santander] Backend Python en producción',
        'Develop and maintain web applications using Python for backend services',
        'línea T-01 de la oferta · instancia de plantilla-microservicio-ia', '02-backend-api', 'abierto',
        'IA:05-arquitecto-sypnose:claude-opus-5', 'H:carlos', 'prueba-local/PLAN-CS-T01', '2026-09-15T00:00:00.000Z');
INSERT INTO requisito VALUES ('PLAN-CS-T01', 'R1',
  'Cuando el servicio arranque en modo real y falte una credencial, DEBE fallar antes de readiness con mensaje claro; en modo fake DEBE arrancar sin BD ni LLM.',
  'pytest tests/test_main.py tests/test_engine_mode.py -q');
INSERT INTO tarea (id, plan_id, req_ref, titulo, progreso, agente) VALUES (9, 'PLAN-CS-T01', 'R1', 'Backend Python en producción', 'pendiente', 'IA:02-backend-api:claude-sonnet-5');
INSERT INTO plan_objetivo VALUES ('PLAN-CS-T01', 'proy:vmi3211028:rag-banking-agent', 'objetivo');
