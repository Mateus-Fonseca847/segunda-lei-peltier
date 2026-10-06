// Verificação da Segunda Lei — versão com um sensor (frio = banho de gelo a 0 °C)
// Mesmo código para o Wokwi e para o Arduino real.
// Saída CSV: t_s,Tq_C,Tf_C,V_V  (toda a física é calculada depois, no Python)

#include <OneWire.h>
#include <DallasTemperature.h>

const float T_FRIO      = 0.0;    // banho de gelo: 0 °C enquanto houver gelo
const bool  REF_INTERNA = false;  // no real: true se a tensão do Peltier ficar abaixo de 1 V
const float VREF        = REF_INTERNA ? 1.1 : 5.0;

OneWire barramento(2);            // fio de dados do DS18B20 no pino 2
DallasTemperature sensores(&barramento);
DeviceAddress quente;

void setup() {
  Serial.begin(115200);
  sensores.begin();
  if (!sensores.getAddress(quente, 0)) {
    Serial.println("# ERRO: sensor nao encontrado (confira o fio de dados e o pull-up)");
  }
  sensores.setResolution(quente, 12);           // 0,0625 °C
  analogReference(REF_INTERNA ? INTERNAL : DEFAULT);
  Serial.println("t_s,Tq_C,Tf_C,V_V");
}

void loop() {
  sensores.requestTemperatures();               // ~0,75 s com 12 bits
  float Tq = sensores.getTempC(quente);
  if (Tq == DEVICE_DISCONNECTED_C) {
    Serial.println("# ERRO: leitura do sensor falhou");
    delay(1000);
    return;
  }
  float V = analogRead(A0) * VREF / 1023.0;

  Serial.print(millis() / 1000.0, 3); Serial.print(',');
  Serial.print(Tq, 4);                Serial.print(',');
  Serial.print(T_FRIO, 4);            Serial.print(',');
  Serial.println(V, 4);
}
