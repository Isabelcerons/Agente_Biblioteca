-- ============================================================
-- DATOS DE DEMOSTRACIÓN — ficticios
-- Los nombres de usuarios, autores de tesis y correos son inventados.
-- Los libros son referencias bibliográficas reales para uso académico.
-- ============================================================
-- Ejecutar conectado a biblioteca_agente como agente_biblio.
-- Los materiales se insertan idempotentemente y se conservan para no
-- afectar documentos de conocimiento que pudieran referenciarlos.

BEGIN;

-- Se reinician únicamente los datos operativos de la demostración.
-- No se truncan usuarios ni material: conversaciones conserva su historial
-- con usuario_id en NULL y conocimiento.documentos conserva sus referencias.
TRUNCATE TABLE public.devoluciones, public.multas, public.reservas,
    public.prestamos, public.ejemplares RESTART IDENTITY;
DELETE FROM public.usuarios
WHERE codigo IN (
    '103', '104', '102', '105',
    '106', '107', '108', '101'
);

INSERT INTO public.usuarios (codigo, nombre, tipo, programa, email, activo, es_demo)
VALUES
    ('103', 'Valentina Cárdenas Rojas', 'estudiante', 'Ingeniería de Sistemas', 'valentina.cardenas@demo.itp.edu.co', true, true),
    ('104', 'Juan Sebastián Muñoz Pantoja', 'estudiante', 'Ingeniería de Sistemas', 'juan.munoz@demo.itp.edu.co', true, true),
    ('102', 'Mariana Rosero Burbano', 'estudiante', 'Ingeniería Agroforestal', 'mariana.rosero@demo.itp.edu.co', true, true),
    ('105', 'Andrés Felipe Jojoa Gómez', 'estudiante', 'Administración de Empresas', 'andres.jojoa@demo.itp.edu.co', true, true),
    ('106', 'Laura Camila Insuasty Díaz', 'estudiante', 'Contaduría Pública', 'laura.insuasty@demo.itp.edu.co', true, true),
    ('107', 'Diego Alejandro Chicunque Muñoz', 'estudiante', 'Ingeniería Ambiental', 'diego.chicunque@demo.itp.edu.co', true, true),
    ('108', 'Paola Andrea Zambrano Erazo', 'docente', 'Ingeniería de Sistemas', 'paola.zambrano@demo.itp.edu.co', true, true),
    ('101', 'Carlos Eduardo Córdoba Díaz', 'docente', 'Administración de Empresas', 'carlos.cordoba@demo.itp.edu.co', true, true);

WITH datos(titulo, autor, anio, tipo, tema, programa, editorial, isbn, descripcion_corta) AS (
    VALUES
    ('Cálculo de una variable', 'James Stewart', 2013, 'libro', 'Cálculo', 'Ingeniería de Sistemas', 'Cengage Learning', NULL, 'Presenta los conceptos de cálculo diferencial e integral con ejemplos y problemas aplicados. Incluye funciones, límites, derivadas e integración.'),
    ('Ingeniería de software', 'Ian Sommerville', 2011, 'libro', 'Ingeniería de software', 'Ingeniería de Sistemas', 'Pearson', NULL, 'Explica procesos, requisitos, diseño, pruebas y evolución de sistemas de software. Es una introducción amplia a las prácticas de ingeniería.'),
    ('Redes de computadoras', 'Andrew S. Tanenbaum y David J. Wetherall', 2012, 'libro', 'Redes', 'Ingeniería de Sistemas', 'Pearson', NULL, 'Describe arquitecturas y protocolos de redes desde las capas física y de enlace hasta las aplicaciones. Incluye ejemplos de Internet y redes inalámbricas.'),
    ('Fundamentos de seguridad en redes', 'William Stallings', 2004, 'libro', 'Seguridad de redes', 'Ingeniería de Sistemas', 'Pearson Educación', NULL, 'Introduce los mecanismos y protocolos para la seguridad de redes y comunicaciones. Aborda autenticación, cifrado y control de acceso.'),
    ('Firewalls y redes privadas virtuales', 'William R. Cheswick, Steven M. Bellovin y Aviel D. Rubin', 2003, 'libro', 'Seguridad de redes', 'Ingeniería de Sistemas', 'Addison-Wesley', NULL, 'Estudia arquitecturas de cortafuegos y redes privadas virtuales. Presenta principios de diseño, operación y análisis de tráfico.'),
    ('Hacking ético', 'Carlos Tori', 2008, 'libro', 'Ciberseguridad', 'Ingeniería de Sistemas', 'Buenos Aires: edición del autor', NULL, 'Presenta conceptos de evaluación ética de seguridad y pruebas controladas. Enfatiza el uso responsable de metodologías y herramientas.'),
    ('Seguridad informática: gestión de riesgos', 'Michael E. Whitman y Herbert J. Mattord', 2012, 'libro', 'Ciberseguridad', 'Ingeniería de Sistemas', 'Cengage Learning', NULL, 'Aborda la gestión de riesgos de seguridad de la información, políticas y controles. Ofrece un marco para organizar programas de seguridad.'),
    ('Criptografía y seguridad de redes: principios y prácticas', 'William Stallings', 2011, 'libro', 'Criptografía y seguridad', 'Ingeniería de Sistemas', 'Pearson', NULL, 'Expone técnicas criptográficas, protocolos y aplicaciones para proteger comunicaciones digitales. Incluye conceptos de seguridad de redes.'),
    ('Fundamentos de bases de datos', 'Abraham Silberschatz, Henry F. Korth y S. Sudarshan', 2014, 'libro', 'Bases de datos', 'Ingeniería de Sistemas', 'McGraw-Hill', NULL, 'Introduce modelos de datos, SQL, diseño relacional, transacciones y almacenamiento. Los ejemplos conectan la teoría con sistemas gestores reales.'),
    ('Inteligencia artificial: un enfoque moderno', 'Stuart Russell y Peter Norvig', 2021, 'libro', 'Inteligencia artificial', 'Ingeniería de Sistemas', 'Pearson', NULL, 'Presenta agentes inteligentes, búsqueda, razonamiento, aprendizaje y percepción. Combina fundamentos teóricos con aplicaciones contemporáneas.'),
    ('Ingeniería del software: un enfoque práctico', 'Roger S. Pressman y Bruce R. Maxim', 2015, 'libro', 'Ingeniería de software', 'Ingeniería de Sistemas', 'McGraw-Hill', NULL, 'Recorre las actividades, métodos y herramientas de construcción de software. Trata requisitos, arquitectura, calidad, pruebas y gestión de proyectos.'),
    ('Redes de computadoras: un enfoque descendente', 'James F. Kurose y Keith W. Ross', 2017, 'libro', 'Redes', 'Ingeniería de Sistemas', 'Pearson', NULL, 'Explica redes comenzando por las aplicaciones y avanzando hacia las capas inferiores. Utiliza Internet como hilo conductor de los protocolos.'),
    ('Sistemas operativos: conceptos fundamentales', 'Abraham Silberschatz, Peter B. Galvin y Greg Gagne', 2018, 'libro', 'Sistemas operativos', 'Ingeniería de Sistemas', 'Wiley', NULL, 'Describe procesos, concurrencia, memoria, almacenamiento y protección en sistemas operativos. Incluye principios aplicables a plataformas modernas.'),
    ('Cómo programar en Java', 'Paul Deitel y Harvey Deitel', 2017, 'libro', 'Programación', 'Ingeniería de Sistemas', 'Pearson', NULL, 'Enseña programación orientada a objetos y fundamentos de Java mediante ejemplos progresivos. Incluye estructuras, clases, colecciones y aplicaciones.'),
    ('Sistemas de bases de datos', 'Ramez Elmasri y Shamkant B. Navathe', 2016, 'libro', 'Bases de datos', 'Ingeniería de Sistemas', 'Pearson', NULL, 'Desarrolla modelado entidad-relación, diseño relacional, SQL y bases de datos avanzadas. Incluye ejercicios de implementación y normalización.'),
    ('Fundamentos de programación', 'Luis Joyanes Aguilar', 2008, 'libro', 'Programación', 'Ingeniería de Sistemas', 'McGraw-Hill', NULL, 'Presenta algoritmos, estructuras de control y técnicas básicas de programación. Los ejercicios ayudan a desarrollar soluciones paso a paso.'),
    ('Agroforestería: bases conceptuales y metodológicas', 'Oscar Antonio López', 2007, 'libro', 'Agroforestería', 'Ingeniería Agroforestal', 'Universidad Nacional de Colombia', NULL, 'Introduce los sistemas agroforestales y sus componentes ecológicos y productivos. Revisa criterios para su diseño y evaluación.'),
    ('Sistemas agroforestales: principios y aplicaciones en los trópicos', 'P. K. R. Nair', 1993, 'libro', 'Sistemas agroforestales', 'Ingeniería Agroforestal', 'Kluwer Academic Publishers', NULL, 'Examina principios, clasificación y manejo de sistemas agroforestales tropicales. Presenta alternativas para integrar árboles y cultivos.'),
    ('El suelo: los recursos y la vida', 'Nyle C. Brady y Ray R. Weil', 2016, 'libro', 'Suelos', 'Ingeniería Agroforestal', 'Pearson', NULL, 'Explica las propiedades físicas, químicas y biológicas del suelo. Relaciona su manejo con la producción y la sostenibilidad ambiental.'),
    ('Edafología: uso y protección de los suelos', 'Jaume Porta, Marta López-Acevedo y Carlos Roquero', 2003, 'libro', 'Edafología', 'Ingeniería Agroforestal', 'Mundi-Prensa', NULL, 'Ofrece fundamentos para describir, clasificar y evaluar suelos. Aborda prácticas de conservación y planificación de su uso.'),
    ('Ecología: individuos, poblaciones y comunidades', 'Michael Begon, Colin R. Townsend y John L. Harper', 2006, 'libro', 'Ecología', 'Ingeniería Ambiental', 'Blackwell Publishing', NULL, 'Desarrolla conceptos de ecología desde los organismos hasta las comunidades. Integra teoría, ejemplos y métodos de análisis ecológico.'),
    ('Ecología', 'Eugene P. Odum y Gary W. Barrett', 2005, 'libro', 'Ecología', 'Ingeniería Ambiental', 'Thomson', NULL, 'Presenta principios de funcionamiento de ecosistemas, energía y ciclos de materia. Relaciona procesos ecológicos con la gestión ambiental.'),
    ('Ciencias ambientales: ecología y desarrollo sostenible', 'Bernard J. Nebel y Richard T. Wright', 1999, 'libro', 'Ciencias ambientales', 'Ingeniería Ambiental', 'Pearson', NULL, 'Analiza problemas ambientales, recursos naturales y desarrollo sostenible. Incluye fundamentos de contaminación y conservación.'),
    ('Fundamentos de conservación de suelos y aguas', 'Francisco J. M. M. Morgan', 2005, 'libro', 'Conservación de suelos y aguas', 'Ingeniería Ambiental', 'Mundi-Prensa', NULL, 'Revisa procesos de erosión y técnicas de conservación de suelos y agua. Presenta métodos de evaluación y manejo de cuencas.'),
    ('Administración', 'Stephen P. Robbins y Mary Coulter', 2018, 'libro', 'Administración', 'Administración de Empresas', 'Pearson', NULL, 'Explica las funciones administrativas, la toma de decisiones y el trabajo organizacional. Usa casos para aplicar conceptos de gestión.'),
    ('Administración: una perspectiva global y empresarial', 'Harold Koontz, Heinz Weihrich y Mark Cannice', 2012, 'libro', 'Administración', 'Administración de Empresas', 'McGraw-Hill', NULL, 'Presenta teorías y prácticas de administración en organizaciones globales. Incluye planeación, organización, dirección y control.'),
    ('Administración de recursos humanos', 'Idalberto Chiavenato', 2009, 'libro', 'Recursos humanos', 'Administración de Empresas', 'McGraw-Hill', NULL, 'Aborda procesos de gestión de personas en las organizaciones. Trata selección, capacitación, evaluación y desarrollo del talento.'),
    ('Fundamentos de marketing', 'Philip Kotler y Gary Armstrong', 2017, 'libro', 'Marketing', 'Administración de Empresas', 'Pearson', NULL, 'Introduce el valor para el cliente, la investigación de mercados y la mezcla de marketing. Incluye estrategias para productos, precios y canales.'),
    ('Dirección de marketing', 'Philip Kotler y Kevin Lane Keller', 2016, 'libro', 'Marketing', 'Administración de Empresas', 'Pearson', NULL, 'Desarrolla herramientas para analizar mercados y formular estrategias de marketing. Considera marcas, clientes y creación de valor.'),
    ('Comportamiento organizacional', 'Stephen P. Robbins y Timothy A. Judge', 2013, 'libro', 'Comportamiento organizacional', 'Administración de Empresas', 'Pearson', NULL, 'Analiza cómo las personas y los grupos influyen en las organizaciones. Estudia motivación, liderazgo, comunicación y cultura.'),
    ('Gestión de proyectos', 'Jack Gido, James P. Clements y Rose Baker', 2018, 'libro', 'Gestión de proyectos', 'Administración de Empresas', 'Cengage Learning', NULL, 'Guía la planeación, programación y control de proyectos. Presenta herramientas para administrar alcance, costos, tiempos y equipos.'),
    ('Gestión de empresas', 'Julio García del Junco y Cristóbal Casanueva Rocha', 2000, 'libro', 'Gestión empresarial', 'Administración de Empresas', 'Pirámide', NULL, 'Revisa las áreas funcionales y los principios de gestión de una empresa. Integra conceptos de organización, dirección y estrategia.'),
    ('Contabilidad de costos: un enfoque gerencial', 'Charles T. Horngren, Srikant M. Datar y Madhav V. Rajan', 2012, 'libro', 'Contabilidad de costos', 'Contaduría Pública', 'Pearson', NULL, 'Explica el análisis de costos para apoyar decisiones gerenciales. Incluye costeo por órdenes, procesos y actividades.'),
    ('Contabilidad financiera', 'Gerardo Guajardo Cantú y Nora E. Andrade de Guajardo', 2014, 'libro', 'Contabilidad financiera', 'Contaduría Pública', 'McGraw-Hill', NULL, 'Presenta los fundamentos de registro, preparación e interpretación de estados financieros. Incluye el ciclo contable y normas aplicables.'),
    ('Contabilidad: la base para decisiones gerenciales', 'Walter T. Harrison, Charles T. Horngren y C. William Thomas', 2012, 'libro', 'Contabilidad', 'Contaduría Pública', 'Pearson', NULL, 'Relaciona la información contable con decisiones de gestión. Aborda estados financieros, costos y control interno.'),
    ('Principios de contabilidad generalmente aceptados', 'Javier Romero López', 2010, 'libro', 'Contabilidad', 'Contaduría Pública', 'McGraw-Hill', NULL, 'Reúne conceptos y procedimientos de contabilidad financiera. Expone el registro de operaciones y la elaboración de información contable.'),
    ('Contabilidad de costos', 'Juan García Colín', 2014, 'libro', 'Contabilidad de costos', 'Contaduría Pública', 'McGraw-Hill', NULL, 'Describe sistemas de acumulación y asignación de costos de producción. Incluye herramientas para determinar costos unitarios y controlar operaciones.'),
    ('Principios de administración financiera', 'Lawrence J. Gitman y Chad J. Zutter', 2012, 'libro', 'Finanzas', 'Contaduría Pública', 'Pearson', NULL, 'Introduce decisiones financieras, valor del dinero, riesgo y análisis de estados. Ofrece métodos para evaluar inversiones y financiamiento.'),
    ('Metodología de la investigación', 'Roberto Hernández Sampieri, Carlos Fernández Collado y María del Pilar Baptista Lucio', 2014, 'libro', 'Metodología de la investigación', 'Transversal', 'McGraw-Hill', NULL, 'Explica enfoques cuantitativos, cualitativos y mixtos para desarrollar investigaciones. Guía la formulación de problemas, diseños e informes.'),
    ('La cocina de la escritura', 'Daniel Cassany', 1993, 'libro', 'Comunicación escrita', 'Transversal', 'Anagrama', NULL, 'Ofrece estrategias prácticas para planear, redactar y revisar textos. Promueve una escritura clara y adecuada al propósito comunicativo.')
)
INSERT INTO public.material
    (titulo, autor, anio, tipo, tema, programa, editorial, isbn, descripcion_corta, es_demo)
SELECT d.titulo, d.autor, d.anio, d.tipo, d.tema, d.programa, d.editorial,
       d.isbn, d.descripcion_corta, true
FROM datos AS d
WHERE NOT EXISTS (
    SELECT 1
    FROM public.material AS m
    WHERE m.titulo = d.titulo AND m.autor = d.autor
);

WITH datos(titulo, autor, anio, tema, programa, descripcion_corta) AS (
    VALUES
    ('Evaluación de sistemas agroforestales de cacao en el piedemonte amazónico del Putumayo', 'Natalia Fernanda Coral Burbano', 2018, 'Cacao y sistemas agroforestales', 'Ingeniería Agroforestal', 'Evalúa arreglos agroforestales de cacao en fincas del Putumayo y su aporte a la producción y conservación del suelo.'),
    ('Caracterización de cultivos de sacha inchi en unidades productivas de Mocoa', 'Jhonatan Andrés Pantoja Rosero', 2019, 'Sacha inchi', 'Ingeniería Agroforestal', 'Caracteriza prácticas de cultivo de sacha inchi y aspectos productivos de unidades rurales en el municipio de Mocoa.'),
    ('Diversidad arbórea en sistemas agroforestales amazónicos de Villagarzón', 'María Alejandra Chasoy Jacanamijoy', 2020, 'Biodiversidad agroforestal', 'Ingeniería Agroforestal', 'Documenta la diversidad de árboles asociados con cultivos amazónicos y analiza su función en las fincas estudiadas.'),
    ('Asistente conversacional para orientar trámites académicos en la Institución Universitaria del Putumayo', 'Santiago David Rosas Muñoz', 2021, 'Chatbot académico', 'Ingeniería de Sistemas', 'Diseña un prototipo conversacional para responder consultas frecuentes de estudiantes sobre procesos académicos institucionales.'),
    ('Prototipo IoT para el monitoreo de humedad en cultivos de cacao de Puerto Asís', 'Lina Marcela Guaca Insuasty', 2022, 'Internet de las cosas y agricultura', 'Ingeniería de Sistemas', 'Implementa sensores conectados para registrar humedad en parcelas de cacao. Evalúa la transmisión y visualización de mediciones.'),
    ('Análisis de ciberseguridad en pequeñas empresas comerciales de Mocoa', 'Óscar Mauricio Jojoa Cabrera', 2023, 'Ciberseguridad en pymes', 'Ingeniería de Sistemas', 'Identifica prácticas y riesgos de ciberseguridad en pequeñas empresas de Mocoa y propone recomendaciones de gestión.'),
    ('Prácticas contables en cooperativas de productores rurales del Putumayo', 'Diana Carolina Muñoz Chamorro', 2018, 'Contabilidad cooperativa', 'Contaduría Pública', 'Describe procesos contables de cooperativas rurales y analiza necesidades de información para su gestión financiera.'),
    ('Plan de emprendimiento turístico comunitario para la zona rural de Sibundoy', 'Brayan Esteban Jacanamijoy Tisoy', 2019, 'Emprendimiento turístico', 'Administración de Empresas', 'Formula una propuesta de emprendimiento turístico comunitario con diagnóstico de mercado y criterios de sostenibilidad local.'),
    ('Gestión de residuos sólidos aprovechables en instituciones educativas de Puerto Guzmán', 'Karen Lizeth Burbano Erazo', 2020, 'Gestión de residuos', 'Ingeniería Ambiental', 'Analiza la separación y aprovechamiento de residuos en instituciones educativas y plantea acciones de mejora ambiental.'),
    ('Estrategias de comercialización de cacao producido por asociaciones campesinas de Puerto Caicedo', 'Miguel Ángel Cuéllar Rosero', 2021, 'Comercialización de cacao', 'Administración de Empresas', 'Estudia canales de venta y oportunidades para mejorar la comercialización asociativa del cacao en Puerto Caicedo.'),
    ('Evaluación de calidad del agua en fuentes abastecedoras de comunidades rurales de Orito', 'Paola Andrea Chicunque Taimal', 2022, 'Calidad del agua', 'Ingeniería Ambiental', 'Caracteriza parámetros de calidad de agua en fuentes rurales y relaciona los resultados con prácticas de uso y conservación.'),
    ('Sistema web para el inventario de recursos bibliográficos de una institución universitaria', 'Luis Fernando Córdoba Pantoja', 2023, 'Sistema de información bibliotecario', 'Ingeniería de Sistemas', 'Construye un prototipo web para registrar materiales, ejemplares y consultas de disponibilidad en una colección académica.'),
    ('Análisis financiero de asociaciones productoras de sacha inchi en el Valle de Sibundoy', 'Yuliana Marcela Insuasty Mavisoy', 2024, 'Finanzas rurales', 'Contaduría Pública', 'Examina indicadores financieros y costos de asociaciones productoras de sacha inchi para apoyar decisiones administrativas.'),
    ('Restauración ecológica participativa en áreas ribereñas de la cuenca del río Pepino', 'Daniel Estiven Chasoy Mavisoy', 2024, 'Restauración ecológica', 'Ingeniería Ambiental', 'Propone acciones de restauración ribereña con participación comunitaria y selección de especies nativas del piedemonte amazónico.'),
    ('Modelo de gestión para emprendimientos de turismo de naturaleza en el corredor Mocoa-Sibundoy', 'Angie Tatiana Rosero Burbano', 2025, 'Gestión turística', 'Administración de Empresas', 'Desarrolla un modelo de gestión para emprendimientos de turismo de naturaleza con énfasis en operación responsable y colaboración local.')
)
INSERT INTO public.material
    (titulo, autor, anio, tipo, tema, programa, editorial, isbn, descripcion_corta, es_demo)
SELECT d.titulo, d.autor, d.anio, 'tesis', d.tema, d.programa,
       'Institución Universitaria del Putumayo (repositorio)', NULL,
       d.descripcion_corta, true
FROM datos AS d
WHERE NOT EXISTS (
    SELECT 1
    FROM public.material AS m
    WHERE m.titulo = d.titulo AND m.autor = d.autor
);

-- Los libros más consultados tienen tres ejemplares, los demás dos y cada tesis uno: 103 ejemplares.
WITH objetivo AS (
    SELECT m.id, m.titulo, m.autor, m.tipo,
           CASE
               WHEN m.tipo = 'tesis' THEN 1
               WHEN m.titulo IN (
                   'Cálculo de una variable',
                   'Ingeniería de software',
                   'Redes de computadoras',
                   'Fundamentos de seguridad en redes',
                   'Fundamentos de bases de datos',
                   'Metodología de la investigación',
                   'Fundamentos de marketing',
                   'Contabilidad de costos: un enfoque gerencial'
               ) THEN 3
               ELSE 2
           END AS cantidad
    FROM public.material AS m
    WHERE m.es_demo = true
      AND (
          m.titulo IN (
              'Cálculo de una variable', 'Ingeniería de software', 'Redes de computadoras',
              'Fundamentos de seguridad en redes', 'Firewalls y redes privadas virtuales',
              'Hacking ético', 'Seguridad informática: gestión de riesgos',
              'Criptografía y seguridad de redes: principios y prácticas',
              'Fundamentos de bases de datos', 'Inteligencia artificial: un enfoque moderno',
              'Ingeniería del software: un enfoque práctico',
              'Redes de computadoras: un enfoque descendente',
              'Sistemas operativos: conceptos fundamentales', 'Cómo programar en Java',
              'Sistemas de bases de datos', 'Fundamentos de programación',
              'Agroforestería: bases conceptuales y metodológicas',
              'Sistemas agroforestales: principios y aplicaciones en los trópicos',
              'El suelo: los recursos y la vida', 'Edafología: uso y protección de los suelos',
              'Ecología: individuos, poblaciones y comunidades', 'Ecología',
              'Ciencias ambientales: ecología y desarrollo sostenible',
              'Fundamentos de conservación de suelos y aguas',
              'Administración', 'Administración: una perspectiva global y empresarial',
              'Administración de recursos humanos', 'Fundamentos de marketing',
              'Dirección de marketing', 'Comportamiento organizacional', 'Gestión de proyectos',
              'Gestión de empresas', 'Contabilidad de costos: un enfoque gerencial',
              'Contabilidad financiera', 'Contabilidad: la base para decisiones gerenciales',
              'Principios de contabilidad generalmente aceptados', 'Contabilidad de costos',
              'Principios de administración financiera', 'Metodología de la investigación',
              'La cocina de la escritura',
              'Evaluación de sistemas agroforestales de cacao en el piedemonte amazónico del Putumayo',
              'Caracterización de cultivos de sacha inchi en unidades productivas de Mocoa',
              'Diversidad arbórea en sistemas agroforestales amazónicos de Villagarzón',
              'Asistente conversacional para orientar trámites académicos en la Institución Universitaria del Putumayo',
              'Prototipo IoT para el monitoreo de humedad en cultivos de cacao de Puerto Asís',
              'Análisis de ciberseguridad en pequeñas empresas comerciales de Mocoa',
              'Prácticas contables en cooperativas de productores rurales del Putumayo',
              'Plan de emprendimiento turístico comunitario para la zona rural de Sibundoy',
              'Gestión de residuos sólidos aprovechables en instituciones educativas de Puerto Guzmán',
              'Estrategias de comercialización de cacao producido por asociaciones campesinas de Puerto Caicedo',
              'Evaluación de calidad del agua en fuentes abastecedoras de comunidades rurales de Orito',
              'Sistema web para el inventario de recursos bibliográficos de una institución universitaria',
              'Análisis financiero de asociaciones productoras de sacha inchi en el Valle de Sibundoy',
              'Restauración ecológica participativa en áreas ribereñas de la cuenca del río Pepino',
              'Modelo de gestión para emprendimientos de turismo de naturaleza en el corredor Mocoa-Sibundoy'
          )
      )
),
copias AS (
    SELECT o.id AS material_id, o.titulo, o.autor, serie.numero AS copia
    FROM objetivo AS o
    CROSS JOIN LATERAL generate_series(1, o.cantidad) AS serie(numero)
),
codigos AS (
    SELECT material_id, copia, row_number() OVER (ORDER BY titulo, autor, copia) AS consecutivo
    FROM copias
)
INSERT INTO public.ejemplares (material_id, codigo_barras, estante, estado)
SELECT material_id,
       'BIB-' || lpad(consecutivo::text, 6, '0'),
       chr(65 + ((consecutivo - 1)::integer / 30)) || '-' || lpad((((consecutivo - 1)::integer % 30) / 5 + 1)::text, 2, '0'),
       'disponible'
FROM codigos;

-- Los préstamos se relacionan por código y título, no por identificadores fijos.
WITH datos(titulo, codigo_usuario, dias_desde_prestamo, renovaciones, estado, dias_hasta_vencimiento) AS (
    VALUES
        ('Cálculo de una variable', '103', 2, 3, 'activo', 6),
        ('Redes de computadoras', '104', 1, 1, 'activo', 7),
        ('Ingeniería de software', '105', 3, 0, 'activo', 5),
        ('Fundamentos de bases de datos', '106', 0, 0, 'activo', 8),
        ('Fundamentos de seguridad en redes', '102', 13, 0, 'vencido', -5),
        ('Inteligencia artificial: un enfoque moderno', '107', 20, 0, 'devuelto', -12)
)
INSERT INTO public.prestamos
    (ejemplar_id, usuario_id, fecha_prestamo, fecha_vencimiento, renovaciones, estado)
SELECT e.id,
       u.id,
       current_date - d.dias_desde_prestamo,
       current_date + d.dias_hasta_vencimiento,
       d.renovaciones,
       d.estado
FROM datos AS d
JOIN public.usuarios AS u ON u.codigo = d.codigo_usuario
JOIN public.material AS m ON m.titulo = d.titulo
CROSS JOIN LATERAL (
    SELECT ejemplar.id
    FROM public.ejemplares AS ejemplar
    WHERE ejemplar.material_id = m.id
    ORDER BY ejemplar.codigo_barras
    LIMIT 1
) AS e;

UPDATE public.ejemplares AS e
SET estado = 'prestado'
FROM public.prestamos AS p
WHERE p.ejemplar_id = e.id
  AND p.estado IN ('activo', 'vencido');

INSERT INTO public.devoluciones (prestamo_id, fecha_devolucion, dias_retraso)
SELECT p.id, current_date - 10, 2
FROM public.prestamos AS p
JOIN public.usuarios AS u ON u.id = p.usuario_id
WHERE u.codigo = '107'
  AND p.estado = 'devuelto';

INSERT INTO public.multas (usuario_id, prestamo_id, valor, dias, estado, fecha)
SELECT p.usuario_id, p.id, 5000, 5, 'pendiente', current_date - 5
FROM public.prestamos AS p
JOIN public.usuarios AS u ON u.id = p.usuario_id
WHERE u.codigo = '102'
  AND p.estado = 'vencido';

INSERT INTO public.multas (usuario_id, prestamo_id, valor, dias, estado, fecha)
SELECT p.usuario_id, p.id, 2000, 2, 'pagada', current_date - 10
FROM public.prestamos AS p
JOIN public.usuarios AS u ON u.id = p.usuario_id
WHERE u.codigo = '107'
  AND p.estado = 'devuelto';

-- La reserva de 108 es sobre el libro prestado a 104.
INSERT INTO public.reservas
    (usuario_id, material_id, ejemplar_id, fecha_reserva, expira_en, estado)
SELECT u.id, m.id, NULL, now(), now() + interval '48 hours', 'activa'
FROM public.usuarios AS u
CROSS JOIN public.material AS m
WHERE u.codigo = '108'
  AND m.titulo = 'Redes de computadoras'
  AND m.autor = 'Andrew S. Tanenbaum y David J. Wetherall';

COMMIT;

-- ============================================================
-- ESCENARIOS DE PRUEBA
-- Usuario sin problemas: 101.
-- Usuario con multa pendiente: 102 (multa de 5 días por $5.000).
-- Usuario con préstamo de 3 renovaciones: 103.
-- Préstamo bloqueado por reserva ajena: 104;
-- la reserva la mantiene 108 sobre Redes de computadoras.
-- ============================================================
