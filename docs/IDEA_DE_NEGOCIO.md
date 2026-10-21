# AdaptMobile — Idea de negocio

## Problema
Los equipos que desarrollan apps móviles no saben con certeza qué teléfonos podrán ejecutar su proyecto.
Averiguarlo exige probar en dispositivos físicos o revisar fichas técnicas dispersas, y cada mercado
(México, Estados Unidos, Canadá) vende modelos distintos. El resultado: tiempo perdido, apps lentas o
que fallan en los teléfonos de sus usuarios.

## Solución
**AdaptMobile** es un servicio web que analiza un solo archivo del proyecto (`package.json`, `pubspec.yaml`,
`build.gradle`, `README.md`, etc.). Una IA estima los requisitos aproximados (RAM, CPU, GPU, API gráfica y
versión mínima del sistema) y los cruza con un catálogo real de teléfonos para clasificar cada modelo como
**compatible**, **compatible con limitaciones** o **no compatible**. El usuario también puede preguntar por
un teléfono concreto y recibe una respuesta basada solo en datos verificados del catálogo.

## Usuario final
Desarrolladores independientes, equipos de startups, personas de control de calidad (QA) y estudiantes
de desarrollo móvil que necesitan decidir qué dispositivos soportar antes de publicar.

## Valor agregado
- **Datos reales:** usa un dataset de fichas de teléfonos; no inventa modelos ni especificaciones.
- **Por mercado:** filtra el catálogo por región (MX, US, CA) y por antigüedad del dispositivo.
- **IA privada y económica:** funciona con un modelo local (Ollama), por lo que el código del cliente no
  tiene que enviarse a un tercero, y reduce el consumo de tokens al prefiltrar en la base de datos.
- **Respuestas honestas:** si el teléfono no está en la base verificada, lo dice en lugar de inventar.
- **Resiliente:** si la IA no responde, un motor determinista de respaldo entrega una estimación.

## Modelo de ingresos
Plan gratuito (2 análisis o preguntas al mes) y planes de pago por mayor uso. La estructura de
suscripciones ya existe en la aplicación; la pasarela de pagos está preparada pero todavía no activa.

## Alcance y límites
Los requisitos son estimaciones a partir de un archivo, no mediciones; el catálogo es una foto en el tiempo
y la compatibilidad de bandas en México se infiere con reglas configurables.
