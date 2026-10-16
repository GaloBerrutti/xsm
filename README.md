# XSM

Bot de trading sobre futuros perpetuos de criptomonedas en Bybit. Cada lunes ordena las 30 monedas con más volumen
según cuánto subieron o bajaron en el último mes, compra las 6 más fuertes y vende en corto las 6 más débiles, con el
mismo capital de cada lado. Gana si lo comprado rinde más que lo vendido, suba o baje el mercado.

Este repositorio es el registro público del bot. Cada cartera se sube en el momento en que el bot la decide y el
resultado se calcula con los precios públicos de Bybit. El código del bot no está acá: están sus decisiones y la forma
de comprobar el resultado.

Registro en vivo: **[galoberrutti.github.io/xsm](https://galoberrutti.github.io/xsm/)**

Corre en una cuenta simulada, sin dinero real, desde el 19 de octubre de 2026.

## Cómo opera

- Arma la cartera una vez por semana, los lunes a las 00:10 UTC. Lo que sigue en la cartera del mismo lado se
  mantiene y lo que sale se cierra.
- Entra con órdenes límite por debajo del cierre del lunes en las compras y por encima en las ventas en corto, más
  lejos cuanto más se mueve cada moneda. Si en la semana el precio no llega, la orden se cancela y esa parte de la
  cuenta queda sin usar.
- Sale al lunes siguiente, cuando arma la cartera nueva.
- 6 compras y 6 ventas en corto, la mitad de la cuenta de cada lado. Sin apalancamiento, cada posición es el 8,3 %
  de la cuenta.
- No usa stop loss ni take profit. El riesgo se controla con el tamaño de cada posición y con las dos patas
  compensándose entre sí. Con stops de 5 a 30 % por posición el backtest rinde bastante menos (con 10 %, pasa de
  +19,9 % a -18,4 % por año): en la semana el precio se mueve lo suficiente para hacer saltar el stop en posiciones
  que el lunes terminan a favor.

## Qué se publica

| archivo | contenido | cuándo |
|---|---|---|
| `datos/ordenes/AAAA-MM-DD.json` | la cartera de la semana: par, lado, peso, cierre del lunes y precio límite de cada orden, o `sigue` si la posición viene de la semana anterior | el lunes a las 00:10 UTC |
| `datos/cierres/AAAA-MM-DD.json` | qué orden se llenó y a qué hora, precios de entrada y salida, financiación y resultado de cada posición | minutos después de que empieza la semana siguiente |
| `datos/historial.csv` | una fila por semana cerrada: resultado, acumulado y caída desde el máximo | con cada cierre |
| `datos/indice.json` | las semanas publicadas y las cerradas | con cada publicación |
| `verificar.py` | recalcula las semanas cerradas con los precios de Bybit | |
| `index.html`, `app.js`, `estilo.css` | la página, que pide los precios a Bybit desde el navegador de quien la mira | |

Un archivo publicado no se vuelve a modificar. Cualquier cambio quedaría a la vista en el historial de commits.

## Cómo se comprueba

Cada semana empieza a contar dos minutos después de que su archivo de órdenes llega a GitHub (`inicio_utc`), así que
todo lo que entra en el resultado pasó con las órdenes ya publicadas. GitHub registra la hora en que recibe cada push
y la página la muestra para la semana en curso.

Para recalcular las semanas cerradas y compararlas con lo publicado:

```
python verificar.py              # todas
python verificar.py 2026-10-19   # una sola
```

Usa solo la biblioteca estándar de Python y no pide cuenta ni claves. En la página, el botón "recalcular" de cada
semana hace la misma cuenta en el navegador.

### Reglas de la cuenta

- Cada posición lleva 1/12 de la cuenta al empezar la semana (`peso`), sin apalancamiento.
- Una compra se llena en el primer minuto cuyo mínimo llega al precio límite y una venta en corto en el primer minuto
  cuyo máximo llega. Se llena al precio límite.
- Una orden puede llenarse hasta el `corte_utc` de la semana siguiente, que es el minuto en que se publica la cartera
  nueva. Si no llega, se cancela.
- Una posición marcada `sigue` ya estaba abierta del mismo lado: entra al precio de apertura del minuto `inicio_utc`,
  sin comisión.
- Todo se valúa al precio de apertura del minuto `inicio_utc` de la semana siguiente. Lo que no sigue se cierra ahí.
- Comisión de 0,10 % del tamaño al entrar y al salir, y la financiación real de cada contrato en cada cobro que pasa
  con la posición abierta.
- Resultado de una posición: el peso por la variación del precio (con el signo del lado), menos las comisiones y la
  financiación pagada.

## Backtest

Bybit, del 16 de agosto de 2021 al 31 de agosto de 2026, con comisión de 0,10 % por operación y la financiación real
de cada contrato. Empieza en agosto de 2021 porque antes Bybit no tenía suficientes monedas para armar la cartera.
Supone entrada a precio de mercado; con órdenes límite rindió algo más, pero la diferencia no es concluyente y se deja
la versión más conservadora.

| cuenta | cada posición | las 12 suman | US$ 5.000 terminan en | rendimiento promedio anual |
|---|--:|--:|--:|--:|
| sin apalancar | 8,3 % | 100 % | US$ 12.473 | +19,9 % |
| 1,5x | 12,5 % | 150 % | US$ 16.090 | +26,1 % |
| 2x | 16,7 % | 200 % | US$ 18.143 | +29,1 % |
| S&P 500 con dividendos (SPY) | | | US$ 9.230 | +12,9 % |

En los 5 años del backtest:

| cuenta | mayor subida | mayor bajada | mejor racha | peor racha |
|---|--:|--:|--:|--:|
| sin apalancar | +17,3 % | -14,0 % | +341,5 % | -45,2 % |
| 1,5x | +26,0 % | -21,0 % | +699,6 % | -61,5 % |
| 2x | +34,6 % | -28,1 % | +1.216,9 % | -74,1 % |
| S&P 500 | +6,6 % | -9,1 % | +129,2 % | -24,5 % |

La mayor subida y la mayor bajada son la mejor y la peor semana, de lunes a lunes. La mejor racha es la mayor suba
desde un mínimo hasta un máximo posterior, y la peor racha, la mayor caída desde un máximo hasta un mínimo posterior.

- Las tres cuentas estuvieron por debajo de lo invertido desde agosto de 2021 hasta diciembre de 2023. Las
  apalancadas volvieron a quedar debajo más tarde: la de 1,5x por última vez en octubre de 2024 y la de 2x en febrero
  de 2026.
- Con aportes de US$ 250 por mes además de los US$ 5.000 iniciales (US$ 20.000 invertidos en total): sin apalancar
  US$ 51.944, 1,5x US$ 74.535, 2x US$ 98.683 y S&P 500 US$ 33.094.
- Más allá de 2x no conviene: la peor racha pasa del 80 % y el rendimiento por año deja de subir.
- El costo real de operar, medido sobre las operaciones ejecutadas en Bybit en 234 lunes, dio alrededor de 0,07 % por
  operación, menos que el 0,10 % que usa el backtest.

## Riesgo y apalancamiento

- El apalancamiento es la suma de las posiciones contra el saldo. La palanca que Bybit deja elegir en cada contrato
  solo define cuánto margen se reserva: una posición de US$ 417 es la misma apuesta con la palanca en 1x o en 10x.
- El backtest supone margen cruzado, que es el modo por defecto de la cuenta unificada de Bybit. Todo el saldo
  respalda todas las posiciones, así que para liquidar la cuenta habría que perder casi todo el saldo en una misma
  semana. La peor semana fue -14,0 % sin apalancar y -28,1 % a 2x. La peor posición del backtest fue una venta en
  corto en BONK que subió 128 % y le costó a la cuenta 10,7 %.
- En margen aislado cada posición se liquida sola: a 2x, con un movimiento de alrededor de 50 % en contra en la
  semana.
- Cada lunes las posiciones se recalculan sobre el saldo de ese momento, así que después de una mala racha el bot opera
  más chico.
- La correlación semanal con Bitcoin fue +0,04 y con el S&P 500, -0,10.

El backtest no garantiza resultados futuros. No es una recomendación de inversión.
