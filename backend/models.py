"""
Modelos SQLAlchemy — SGO Cantera Eldorado v3
Implementa la Sección 14 (Esquema físico) de Ontologia_Cantera_Eldorado_v2.md.

Regla de estilo aplicada en toda la base (Sección 14, párrafo 1):
id interno autoincremental como PK en TODAS las tablas; el código de negocio
(codigo) va como columna UNIQUE, nunca como PK. Evita repetir el problema
que tenía Persona/legajo en el diseño original.
"""
from sqlalchemy import (
    Column, Integer, Float, Text, ForeignKey, UniqueConstraint, Index, text
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()
NOW = text("(datetime('now'))")


# ═══════════════════════ OBJECT TYPES ═══════════════════════

class Planta(Base):
    __tablename__ = "plantas"
    id = Column(Integer, primary_key=True)
    codigo = Column(Text, unique=True, nullable=False)
    nombre = Column(Text, nullable=False)
    estado = Column(Text, nullable=False, server_default="pendiente")  # activa|piloto|pendiente|inactiva
    notas = Column(Text)
    created_at = Column(Text, server_default=NOW)


class ConvenioColectivo(Base):
    """Object Type nuevo — Sección 13/14. Antes era un string repetido en 3 tablas."""
    __tablename__ = "convenios_colectivos"
    id = Column(Integer, primary_key=True)
    codigo = Column(Text, unique=True, nullable=False)  # UOCRA, COMERCIO
    nombre = Column(Text, nullable=False)
    tiene_fondo_cese_laboral = Column(Integer, server_default="0")
    regimen_indemnizatorio = Column(Text)
    sindicato = Column(Text)
    obra_social = Column(Text)


class FuncionOrganizacional(Base):
    """Object Type nuevo — Sección 14. Antes 'Comercial' era texto suelto."""
    __tablename__ = "funciones_organizacionales"
    id = Column(Integer, primary_key=True)
    codigo = Column(Text, unique=True, nullable=False)
    nombre = Column(Text, nullable=False)
    descripcion = Column(Text)


class Puesto(Base):
    __tablename__ = "puestos"
    id = Column(Integer, primary_key=True)
    codigo = Column(Text, unique=True, nullable=False)
    nombre = Column(Text, nullable=False)
    area = Column(Text, nullable=False)
    nivel = Column(Text, nullable=False)
    cardinalidad_esperada = Column(Text, nullable=False, server_default="unica_en_la_empresa")
    # 'unica_en_la_empresa' | 'una_por_planta_activa' — reemplaza es_por_planta (Sección 10.2)
    proposito = Column(Text)
    limites_autoridad = Column(Text)
    convenio_id = Column(Integer, ForeignKey("convenios_colectivos.id"))
    version = Column(Integer, server_default="1")
    vigente = Column(Integer, server_default="1")
    created_at = Column(Text, server_default=NOW)
    updated_at = Column(Text, server_default=NOW)

    convenio = relationship("ConvenioColectivo")


class Persona(Base):
    __tablename__ = "personas"
    id = Column(Integer, primary_key=True)  # identidad propia — NO legajo (Sección 10.3)
    nombre = Column(Text, nullable=False)
    apellido = Column(Text, nullable=False)
    legajo = Column(Text)  # nullable — puede no existir todavía
    cuit = Column(Text)
    convenio_id = Column(Integer, ForeignKey("convenios_colectivos.id"))
    antiguedad_anos = Column(Float)
    estado_legajo = Column(Text, server_default="completo")  # completo|incompleto|sin_legajo
    notas = Column(Text)
    activo = Column(Integer, server_default="1")
    created_at = Column(Text, server_default=NOW)

    convenio = relationship("ConvenioColectivo")
    # nota: NO hay planta_id acá — la planta "de referencia" se deriva de la
    # Asignación activa, no se guarda por duplicado (disciplina de la Sección 12, punto 3).


class Actividad(Base):
    __tablename__ = "actividades"
    id = Column(Integer, primary_key=True)
    codigo = Column(Text, unique=True, nullable=False)
    descripcion = Column(Text, nullable=False)
    area = Column(Text, nullable=False)
    nivel = Column(Text, nullable=False)
    competencia = Column(Text)
    es_critica = Column(Integer, server_default="0")
    frecuencia = Column(Text)
    notas = Column(Text)
    activo = Column(Integer, server_default="1")
    puesto_codigo = Column(Text, ForeignKey("puestos.codigo"))  # se_origina_en (Link Type)
    funcion_organizacional_id = Column(Integer, ForeignKey("funciones_organizacionales.id"))  # nullable
    created_at = Column(Text, server_default=NOW)
    updated_at = Column(Text, server_default=NOW)
    # nota: NO hay columna convenio acá — se elimina, era redundante (Sección 12, punto 3).

    puesto = relationship("Puesto", foreign_keys=[puesto_codigo])
    funcion = relationship("FuncionOrganizacional")


class TipoDeCapacitacion(Base):
    __tablename__ = "tipos_de_capacitacion"
    id = Column(Integer, primary_key=True)
    codigo = Column(Text, unique=True)
    nombre = Column(Text, nullable=False)
    organismo_emisor = Column(Text)   # nuevo — ej. "ANMAC"
    vigencia_meses = Column(Integer)  # nuevo — nullable si no vence
    tipo = Column(Text, server_default="documento")  # documento|curso|habilitacion
    descripcion = Column(Text)
    url_o_referencia = Column(Text)
    duracion_estimada = Column(Text)
    created_at = Column(Text, server_default=NOW)


class Procedimiento(Base):
    __tablename__ = "procedimientos"
    id = Column(Integer, primary_key=True)
    codigo = Column(Text, unique=True, nullable=False)
    nombre = Column(Text, nullable=False)
    area = Column(Text, nullable=False)
    nivel_riesgo = Column(Text, server_default="medio")
    descripcion = Column(Text)
    tiene_nivel_urgente = Column(Integer, server_default="1")
    tiene_nivel_emergencia = Column(Integer, server_default="1")
    formularios_asociados = Column(Text)  # JSON array
    vigente = Column(Integer, server_default="1")  # Fase 3 — baja lógica, igual que Puesto/Mecanismo
    created_at = Column(Text, server_default=NOW)


class PasoDeProcedimiento(Base):
    __tablename__ = "pasos_procedimiento"
    id = Column(Integer, primary_key=True)
    procedimiento_id = Column(Integer, ForeignKey("procedimientos.id"), nullable=False)
    numero = Column(Integer, nullable=False)
    titulo = Column(Text, nullable=False)
    descripcion = Column(Text, nullable=False)
    responsable_puesto_codigo = Column(Text, ForeignKey("puestos.codigo"))  # antes texto libre
    responsable_texto_original = Column(Text)  # cuando el texto no resuelve a un solo puesto (ej. "PRD-02 → DIR-03", "PRD-02 + ADM-06")
    documento = Column(Text)


class Indicador(Base):
    __tablename__ = "indicadores"
    id = Column(Integer, primary_key=True)
    codigo = Column(Text, unique=True, nullable=False)
    nombre = Column(Text, nullable=False)
    area = Column(Text, nullable=False)
    formula = Column(Text)
    frecuencia = Column(Text)
    fuente_dato = Column(Text)
    responsable_carga_puesto_codigo = Column(Text, ForeignKey("puestos.codigo"))  # antes texto libre
    responsable_uso_puesto_codigo = Column(Text, ForeignKey("puestos.codigo"))    # antes texto libre
    umbral_verde = Column(Text)
    umbral_amarillo = Column(Text)
    umbral_rojo = Column(Text)
    activo = Column(Integer, server_default="1")


class MedicionDeIndicador(Base):
    """Reemplaza kpi_valores. Se quita 'semaforo' — se calcula al vuelo (Función 6, Sección 10.4)."""
    __tablename__ = "mediciones_indicador"
    id = Column(Integer, primary_key=True)
    indicador_id = Column(Integer, ForeignKey("indicadores.id"), nullable=False)  # antes 'codigo' texto
    periodo = Column(Text, nullable=False)
    valor = Column(Text)
    notas = Column(Text)
    created_at = Column(Text, server_default=NOW)
    __table_args__ = (UniqueConstraint("indicador_id", "periodo"),)


class Perfil(Base):
    """Object Type agregado en Sección 13.1 — cubre el caso Cholín y los 'ajustes individuales'."""
    __tablename__ = "perfiles"
    id = Column(Integer, primary_key=True)
    nombre = Column(Text, nullable=False)
    estado = Column(Text, server_default="borrador")  # borrador|vigente|archivado
    origen = Column(Text, server_default="armado")     # armado|individual
    descripcion = Column(Text)
    creado_por = Column(Text, server_default="sistema")
    created_at = Column(Text, server_default=NOW)
    updated_at = Column(Text, server_default=NOW)


class Mecanismo(Base):
    """Object Type agregado en Sección 13.2 — los 23 de la Parte III."""
    __tablename__ = "mecanismos"
    id = Column(Integer, primary_key=True)
    codigo = Column(Text, unique=True, nullable=False)  # MC-01..MC-23
    nombre = Column(Text, nullable=False)
    grupo = Column(Text, nullable=False)  # diario|semanal|mensual|evento|emergencia
    frecuencia = Column(Text)
    descripcion = Column(Text)
    documento = Column(Text)
    emite = Column(Text)   # se mantiene como texto de referencia (ver MecanismoPuesto para el vínculo real)
    recibe = Column(Text)
    estado_relevado = Column(Text)
    vigente = Column(Integer, server_default="1")
    created_at = Column(Text, server_default=NOW)


class Formulario(Base):
    """Object Type agregado en Fase 2 (2/10/2026) — Entrega C del Manual de
    Procedimientos (F-01 a F-11). Reemplaza el campo de texto suelto
    procedimientos.formularios_asociados, que queda en desuso sin eliminarse
    (evita un ALTER TABLE destructivo sobre SQLite sin necesidad real).
    Es metadata simple sin historia encadenada — a diferencia del resto de
    los objetos, admite borrado físico real (ver ui_formularios.py)."""
    __tablename__ = "formularios"
    id = Column(Integer, primary_key=True)
    codigo = Column(Text, unique=True, nullable=False)  # F-01..F-11
    nombre = Column(Text, nullable=False)
    origen = Column(Text)      # Tango | Mixto | Físico/Planilla
    emisor = Column(Text)
    receptor = Column(Text)
    frecuencia = Column(Text)
    created_at = Column(Text, server_default=NOW)
    updated_at = Column(Text, server_default=NOW)


# ═══════════════════════ JUNCTION OBJECTS ═══════════════════════

class Asignacion(Base):
    """El objeto puente central. Puesto XOR Perfil — nunca ambos, nunca ninguno.
    etapa (Sección 10.2) distingue línea de producción para Trituración y
    Carga y Acarreo, que tienen más de una Asignación activa simultánea."""
    __tablename__ = "asignaciones"
    id = Column(Integer, primary_key=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=False)
    puesto_codigo = Column(Text, ForeignKey("puestos.codigo"))   # nullable — XOR con perfil_id
    perfil_id = Column(Integer, ForeignKey("perfiles.id"))       # nullable — XOR con puesto_codigo
    planta_id = Column(Integer, ForeignKey("plantas.id"), nullable=False)
    etapa = Column(Text)  # nullable: 'primaria' | 'secundaria'
    estado = Column(Text, server_default="activa")  # activa|transicion|finalizada
    fecha_inicio = Column(Text)
    fecha_fin_estimada = Column(Text)
    fecha_fin_real = Column(Text)
    condicion_salida = Column(Text)
    created_at = Column(Text, server_default=NOW)

    persona = relationship("Persona")
    puesto = relationship("Puesto", foreign_keys=[puesto_codigo])
    perfil = relationship("Perfil")
    planta = relationship("Planta")


class HabilitacionDePersona(Base):
    """Reemplaza 'habilitaciones'. El campo tipo deja de ser texto libre."""
    __tablename__ = "habilitaciones_persona"
    id = Column(Integer, primary_key=True)
    persona_id = Column(Integer, ForeignKey("personas.id"), nullable=False)
    tipo_capacitacion_id = Column(Integer, ForeignKey("tipos_de_capacitacion.id"), nullable=False)
    numero = Column(Text)
    fecha_obtencion = Column(Text)
    fecha_vencimiento = Column(Text)
    estado = Column(Text, server_default="vigente")  # vigente|vencida|sin_confirmar


class RolDeTransicion(Base):
    """Reemplaza es_transitorio + condicion_salida de Puesto (Sección 13/Caso 4 de la ontología)."""
    __tablename__ = "roles_transicion"
    id = Column(Integer, primary_key=True)
    puesto_id = Column(Integer, ForeignKey("puestos.id"), unique=True, nullable=False)
    fecha_estimada_extincion = Column(Text)
    condicion_extincion = Column(Text)
    puesto_absorbente_codigo = Column(Text, ForeignKey("puestos.codigo"))
    puesto_monitor_codigo = Column(Text, ForeignKey("puestos.codigo"))
    estado = Column(Text, server_default="vigente")  # vigente|extinguido


class MecanismoPuesto(Base):
    """Junction object — 'rol' es una property propia (Paso 5 del método)."""
    __tablename__ = "mecanismo_puestos"
    id = Column(Integer, primary_key=True)
    mecanismo_id = Column(Integer, ForeignKey("mecanismos.id"), nullable=False)
    puesto_codigo = Column(Text, ForeignKey("puestos.codigo"), nullable=False)
    rol = Column(Text, nullable=False)  # responsable|emite|recibe
    __table_args__ = (UniqueConstraint("mecanismo_id", "puesto_codigo", "rol"),)

    mecanismo = relationship("Mecanismo")


class RegistroDeCumplimiento(Base):
    """Junction object con ciclo de vida propio — mismo patrón que Asignación."""
    __tablename__ = "registro_cumplimiento"
    id = Column(Integer, primary_key=True)
    mecanismo_id = Column(Integer, ForeignKey("mecanismos.id"), nullable=False)
    periodo = Column(Text, nullable=False)
    estado = Column(Text, nullable=False)  # cumplido|cumplido_parcial|no_cumplido
    causa = Column(Text)
    accion_correctiva = Column(Text)
    registrado_por = Column(Text)
    created_at = Column(Text, server_default=NOW)
    __table_args__ = (UniqueConstraint("mecanismo_id", "periodo"),)


# ═══════════════════════ LINK TYPES (tablas puente sin properties propias) ═══════════════════════

class RelacionReporte(Base):
    """Resuelve el Caso 1: reporte jerárquico y coordinación funcional en una sola
    tabla, distinguidos por 'tipo' — evita forzar dos conceptos distintos en un
    solo campo de texto (reporte_a) como estaba antes."""
    __tablename__ = "relaciones_reporte"
    id = Column(Integer, primary_key=True)
    puesto_codigo = Column(Text, ForeignKey("puestos.codigo"), nullable=False)
    relacionado_codigo = Column(Text, ForeignKey("puestos.codigo"), nullable=False)
    tipo = Column(Text, nullable=False)  # jerarquico|funcional
    __table_args__ = (UniqueConstraint("puesto_codigo", "relacionado_codigo", "tipo"),)


class ActividadCapacitacion(Base):
    __tablename__ = "actividad_capacitaciones"
    actividad_id = Column(Integer, ForeignKey("actividades.id"), primary_key=True)
    tipo_capacitacion_id = Column(Integer, ForeignKey("tipos_de_capacitacion.id"), primary_key=True)
    obligatoria = Column(Integer, server_default="1")


class PuestoFuncion(Base):
    __tablename__ = "puesto_funciones"
    puesto_codigo = Column(Text, ForeignKey("puestos.codigo"), primary_key=True)
    funcion_id = Column(Integer, ForeignKey("funciones_organizacionales.id"), primary_key=True)


class PerfilActividad(Base):
    __tablename__ = "perfil_actividades"
    perfil_id = Column(Integer, ForeignKey("perfiles.id"), primary_key=True)
    actividad_id = Column(Integer, ForeignKey("actividades.id"), primary_key=True)
    orden = Column(Integer, server_default="0")


class ActividadCedida(Base):
    """Opción A del reparto de actividades: una actividad de un Puesto que la
    persona titular de ESA Asignación no ejecuta porque la lleva otra persona
    (vía su Perfil individual). La asignación al Puesto se mantiene entera — el
    organigrama no cambia — y la excepción queda registrada y visible."""
    __tablename__ = "actividades_cedidas"
    asignacion_id = Column(Integer, ForeignKey("asignaciones.id"), primary_key=True)
    actividad_id = Column(Integer, ForeignKey("actividades.id"), primary_key=True)
    created_at = Column(Text, server_default=NOW)


class ProcedimientoPuesto(Base):
    __tablename__ = "procedimiento_puestos"
    procedimiento_id = Column(Integer, ForeignKey("procedimientos.id"), primary_key=True)
    puesto_codigo = Column(Text, ForeignKey("puestos.codigo"), primary_key=True)
    rol = Column(Text, server_default="ejecuta")  # ejecuta|aprueba|recibe


class ProcedimientoFormulario(Base):
    """Qué formularios genera o usa cada procedimiento (columna 'Documentos
    generados' del manual) — Fase 2."""
    __tablename__ = "procedimiento_formularios"
    procedimiento_id = Column(Integer, ForeignKey("procedimientos.id"), primary_key=True)
    formulario_id = Column(Integer, ForeignKey("formularios.id"), primary_key=True)


class MecanismoFormulario(Base):
    """Qué formulario es el soporte documental de cada mecanismo (columna
    'Documento' de Mecanismos) — Fase 2."""
    __tablename__ = "mecanismo_formularios"
    mecanismo_id = Column(Integer, ForeignKey("mecanismos.id"), primary_key=True)
    formulario_id = Column(Integer, ForeignKey("formularios.id"), primary_key=True)


# ═══════════════════════ AUDITORÍA ═══════════════════════

class Historial(Base):
    __tablename__ = "historial"
    id = Column(Integer, primary_key=True)
    tabla = Column(Text, nullable=False)
    registro_id = Column(Integer, nullable=False)
    accion = Column(Text, nullable=False)
    datos_anteriores = Column(Text)
    datos_nuevos = Column(Text)
    usuario = Column(Text, server_default="sistema")
    timestamp = Column(Text, server_default=NOW)


# ═══════════════════════ Índices ═══════════════════════
Index("idx_actividades_area", Actividad.area)
Index("idx_actividades_puesto", Actividad.puesto_codigo)
Index("idx_asignaciones_persona", Asignacion.persona_id)
Index("idx_asignaciones_planta", Asignacion.planta_id)
Index("idx_asignaciones_puesto", Asignacion.puesto_codigo)
Index("idx_habilitaciones_vencimiento", HabilitacionDePersona.fecha_vencimiento)
Index("idx_relaciones_reporte_puesto", RelacionReporte.puesto_codigo)
