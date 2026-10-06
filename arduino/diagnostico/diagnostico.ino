// Diagnóstico do sensor DS18B20
// Mostra quantos sensores o Arduino encontra, se o fio vermelho tem 5V
// e a temperatura a cada segundo. Abra o Monitor Serial em 115200.

#include <OneWire.h>
#include <DallasTemperature.h>

OneWire barramento(2);
DallasTemperature sensores(&barramento);

void setup() {
  Serial.begin(115200);
  sensores.begin();
  Serial.print("Sensores encontrados: ");
  Serial.println(sensores.getDeviceCount());
  Serial.print("Sem 5V no fio vermelho (modo parasita): ");
  Serial.println(sensores.isParasitePowerMode() ? "SIM" : "nao");
}

void loop() {
  sensores.requestTemperatures();
  Serial.println(sensores.getTempCByIndex(0));
  delay(1000);
}
