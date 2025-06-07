# Curvas Sistema

**Before**
<br>
Code has been rated at 5.46/10

**After the all code organization**
<br>
Code has been rated at 6.90/10

**After the manual manufacturing**
<br>
Code has been rated at 8.55/10

Foi um grande passo, é quase o mundo ideal que geralmente fica entre 7.50 e 9.00, além disso, a performance da API também melhorou bastante, apesar de ainda ser necessário integrar vários mecanismos de segurança e o mais importante para agora o cache (De preferência, por dicionários para evitar alocação de um servidor adicional para o redis)

## Benchmark

### Werkzeug

* Total de requests: 50.000
* Concorrência: 200
* Requests por segundo: ~714
* Tempo médio de resposta: 278ms
* Falhas: 0

### Gunicorn (20 workers)

* Total de requests: 50.000
* Concorrência: 200
* Requests por segundo: ~8.500
* Tempo médio de resposta: 23 ms
* Falhas: 0

Melhoria em porcentagem de **1089%**

A melhoria foi considerável, mas ainda pode melhorar.