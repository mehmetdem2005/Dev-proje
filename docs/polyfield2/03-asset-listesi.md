# 03 — Polyfield 2 Asset Listesi ve Poligon Bütçeleri

Tüm sayılar **üçgen (tri)** cinsindendir, LOD0 için geçerlidir. Bütçe aşımı, asset'in kabul edilmeme sebebidir — modelciyle "yaklaşık" pazarlığı yapılmaz.

## Özet Tablo

| Kategori | Kalem sayısı | Toplam tahmini iş (adam-gün) |
| --- | --- | --- |
| Karakter ve üniforma | 34 | 95 |
| Silah ve gadget | 58 | 130 |
| Araçlar | 22 | 110 |
| Çevre — modüler bina kiti | 180 | 120 |
| Çevre — doğa | 95 | 55 |
| Çevre — askerî / prop | 140 | 80 |
| VFX | 45 | 40 |
| UI / ikon | 210 | 45 |
| Ses | 320 | 60 |
| **Toplam** | **~1104** | **~735 adam-gün** |

---

## 1. Karakterler (34 kalem — 95 adam-gün)

### Poligon bütçesi

| Seviye | Tri | Kullanım |
| --- | --- | --- |
| LOD0 | 2 400 | 0–25 m |
| LOD1 | 1 200 | 25–60 m |
| LOD2 | 500 | 60–120 m |
| LOD3 | 180 (imposter) | 120 m+ |

Doku: millet başına tek 512×512 atlas. İskelet: **tek paylaşılan rig**, 42 kemik (eller dahil, yüz hariç). Tüm karakterler aynı rig'i kullanır → animasyon bir kez üretilir, herkes kullanır. Bu, üretim planının en kritik kaldıracıdır.

### Kalem listesi

| Millet | Sınıflar (4) | Varyant |
| --- | --- | --- |
| ABD | Piyade, Keskin nişancı (Scout), Tanker, Destek | + Yaz / Kış üst katman |
| Almanya | Piyade, Scout, Tanker, Destek | + Yaz / Kış / Çöl |
| SSCB | Piyade, Scout, Tanker, Destek | + Kış (kaputlu) |
| İngiltere | Piyade, Scout, Tanker, Destek | + Çöl |
| Japonya | Piyade, Scout, Destek | (Pasifik) |

**Modüler karakter yapısı:** Gövde = baş (kask) + torso + kollar + bacaklar + sırt donanımı. Her parça ayrı mesh, çalışma zamanında birleştirilir (mesh combine). 5 millet × 4 sınıf kombinasyonu, 34 benzersiz parça setinden üretilir — 20 ayrı tam karakter modellemek yerine.

**Cephe tutarlılığı kilidi:** Bir maçta bir millet seçildiğinde tüm kask/torso/ekipman parçaları o milletin setinden gelir. Karışım imkânsızdır — Polyfield 1'deki en görünür hata bu yolla yapısal olarak engellenir.

### Animasyon seti (paylaşılan)

| Grup | Klip sayısı |
| --- | --- |
| Hareket (idle/yürü/koş/çömel/sürün, 8 yön) | 26 |
| Silah pozları (7 silah sınıfı × tutuş) | 14 |
| Ateş / şarjör / nişan | 21 |
| Aksiyon (bomba, tırman, atla, kap) | 12 |
| Ölüm / isabet reaksiyonu | 10 |
| **Toplam** | **83 klip** |

---

## 2. Silahlar ve Gadget'lar (58 kalem — 130 adam-gün)

### Poligon bütçesi

| Görünüm | Tri |
| --- | --- |
| Birinci şahıs (viewmodel) | 3 000 |
| Üçüncü şahıs / yerde | 800 |
| Dürbün camı ayrı mesh | 120 |

Doku: silah başına 256×256 veya paylaşılan `weapons_atlas_1024`.

### Silah ağacı — millet bazlı

| Sınıf | ABD | Almanya | SSCB | İngiltere | Japonya |
| --- | --- | --- | --- | --- | --- |
| Tüfek | M1 Garand, Springfield M1903 | Kar98k, Gewehr 43 | Mosin-Nagant, SVT-40 | Lee-Enfield No.4 | Arisaka Type 99 |
| Hafif MT | Thompson M1A1, M3 Grease Gun | MP40, MP507 | PPSh-41, PPS-43 | STEN | Type 100 |
| Otomatik tüfek | BAR-1918A2, M1 Carbine | StG 44, FG 42 | AVS-36 | — | — |
| Makineli | M1919 Browning | MG42, MG34 | DP-28, Maxim | Bren, Vickers | Type 92 |
| Tabanca | M1911 | Walther P38, Luger P08 | TT-33, Nagant M1895 | Webley, Welrod | Nambu Type 14 |
| Tanksavar | Bazooka M1 | Panzerfaust, Panzerschreck | PTRS-41 | PIAT | Type 3 |

**Toplam ateşli silah: 38.** (Polyfield 1'de ~10.)

### Gadget / ekipman (20 kalem)

El bombası (parça tesirli, sis, duman, dumanlı işaret), tanksavar mayını, piyade mayını, tıbbi çanta, cephane kutusu, dürbün, tel makası, kürek (siper kazma), tamir aleti, sabit MG kurulumu, havan (hafif), telsiz (topçu çağrısı), bayrak/işaret direği, sağlık şırıngası, ateş bombası, yapışkan bomba, tuzak teli, gözetleme periskopu, sancak, kalkan levha.

---

## 3. Araçlar (22 kalem — 110 adam-gün)

Polyfield 1'in en büyük eksiğinin kapatıldığı yer.

### Poligon bütçesi

| Sınıf | LOD0 tri | LOD1 | LOD2 | İç mekân (kokpit) |
| --- | --- | --- | --- | --- |
| Ağır tank | 9 000 | 4 000 | 1 400 | 2 500 |
| Orta tank | 7 500 | 3 500 | 1 200 | 2 500 |
| Hafif / yarı paletli | 6 000 | 2 800 | 1 000 | 1 800 |
| Tekerlekli (jeep, kamyon) | 4 500 | 2 000 | 800 | 1 200 |
| Sabit silah (top, uçaksavar) | 3 000 | 1 400 | 600 | — |

### Liste

| Millet | Araçlar |
| --- | --- |
| ABD | Sherman M4A3, Sherman Firefly*, M3 Half-track, Willys Jeep, M8 Greyhound |
| Almanya | Panzer IV, Panther, Tiger I, Jagdpanther*, Sd.Kfz 251, Kübelwagen |
| SSCB | T-34/76, T-34/85, IS-2, GAZ-67, Katyuşa |
| İngiltere | Cromwell, Churchill, Bedford kamyon |
| Ortak | 88 mm uçaksavar/tanksavar, 76 mm sahra topu, Flak 38, sabit MG yuvası |

\* Polyfield 1'den devralınan araçlar.

**Araç parçalanma katmanları:** paletler (ayrı mesh, kopabilir), taret (ayrı pivot), motor bölmesi (duman/yangın durumu), 3 hasar kademesi (temiz / hasarlı / yanmış kabuk).

---

## 4. Çevre — Modüler Bina Kiti (180 kalem — 120 adam-gün)

**1 m ızgara kuralı.** Tüm parçalar 1/2/4/8 m modüllerinde. Pivot daima sol-alt-arka köşede.

| Alt kategori | Parça sayısı | Tri (parça başı) |
| --- | --- | --- |
| Duvar (düz, köşe, pencere, kapı, kırık) | 42 | 40–200 |
| Zemin / tavan / merdiven | 26 | 30–160 |
| Çatı (düz, eğimli, kırık, baca) | 24 | 60–260 |
| Kapı / pencere / kepenk (hareketli) | 18 | 80–200 |
| Sundurma / balkon / merdiven kulesi | 14 | 120–400 |
| Kerpiç seti (Kuzey Afrika) | 22 | 40–220 |
| Ahşap kulübe seti (Pasifik / Doğu) | 20 | 40–200 |
| Yıkıntı parçaları (kırık duvar, çökmüş kat) | 14 | 100–500 |

**Toplam bina LOD0 hedefi:** bir orta boy bina ≤ 6 000 tri. Bir harita üzerinde ≤ 80 bina.

---

## 5. Çevre — Doğa (95 kalem — 55 adam-gün)

| Alt kategori | Adet | Tri | Not |
| --- | --- | --- | --- |
| Ağaç (6 tür × 3 boy) | 18 | 300–900 | Yaprak = düz kart kümesi, alfa kesme |
| Çalı / funda | 12 | 60–200 | Bocage çitinin ana bileşeni |
| Çim kümesi (billboard) | 8 | 12–40 | GPU instancing, Düşük'te kapalı |
| Kaya / kaya kümesi | 16 | 80–500 | 3 biyom varyantı |
| Palmiye / tropik bitki | 10 | 200–600 | Pasifik |
| Kaktüs / çöl bitkisi | 8 | 60–250 | Kuzey Afrika |
| Kütük / devrilmiş ağaç | 9 | 150–400 | Doğal siper |
| Su bitkileri / sazlık | 6 | 40–120 | |
| Kar yığını / buz | 8 | 60–300 | Doğu Cephesi |

Ağaçlar için **rüzgâr:** vertex shader'da tek sinüs salınımı, Düşük profilinde kapalı.

---

## 6. Çevre — Askerî ve Genel Prop (140 kalem — 80 adam-gün)

| Grup | Örnekler | Adet |
| --- | --- | --- |
| İstihkâm | Siper modülleri, kum torbası (5 dizilim), tank engeli (Çek kirpisi), dikenli tel, tahkimat kapısı, bunker girişi, gözetleme kulesi | 34 |
| Lojistik | Yakıt varili, mühimmat sandığı (3 boy), ahşap kasa, çuval, ikmal paleti, telsiz masası, sedye, sahra mutfağı | 26 |
| Kent | Sokak lambası, telefon direği, tabela, otobüs durağı, çeşme, bank, çöp konteyneri, terk edilmiş sivil araç, moloz yığını (6 varyant) | 30 |
| Kırsal | Tahta çit (yıkılabilir), taş duvar, kuyu, saman balyası, ahır kapısı, traktör, saban, hayvan yalağı | 22 |
| Sahil | Çek kirpisi (deniz), rıhtım, iskele, çıkarma gemisi rampası, kayık, deniz feneri | 14 |
| Kilit / hedef | Capture bayrağı (A–E), spawn işareti, radyo anteni, cephanelik | 14 |

**Yıkılabilir işaretli:** varil, sandık, çit, sokak lambası, kum torbası, sivil araç, telefon direği.

---

## 7. VFX (45 kalem — 40 adam-gün)

| Grup | Efekt |
| --- | --- |
| Ateşli silah (10) | Namlu ateşi ×4 (kalibreye göre), kovan atma, mermi izi, isabet toz/metal/ahşap/su/beton |
| Patlama (9) | El bombası, havan, tank mermisi, tanksavar, yakıt varili, mayın, topçu, HE, yangın |
| Duman (6) | Sis bombası, işaret dumanı ×3 renk, araç motor dumanı, bina yangını |
| Çevre (8) | Toz bulutu, yağmur, kar, rüzgârda yaprak, su sıçraması, sis bandı, sıcaklık dalgalanması (çöl), ambient partikül |
| Karakter (7) | İsabet kanı, ayak tozu, nefes buharı (kış), koşu toz izi, iyileşme, ölüm, yeniden doğuş |
| UI-dünya (5) | Capture halkası, hedef işareti, hasar yönü, ping işareti, tamir kıvılcımı |

---

## 8. UI ve İkonlar (210 kalem — 45 adam-gün)

- Silah ikonları (58), gadget ikonları (20), araç ikonları (22), sınıf ikonları (5), millet arması (5)
- HUD parçaları: pusula, sağlık, cephane, capture rozeti (A–E), mini harita, öldürme akışı, hasar göstergesi (36)
- Menü ekranları: ana menü, lobi, sınıf seçimi, harita tarayıcısı, ayarlar, istatistik, editör paneli (24)
- Editör araç ikonları (40)

Tüm ikonlar tek stil: 2 px kalınlıkta hat, dolgu yok, 64×64 SVG kaynak → runtime atlas.

---

## 9. Ses (320 kalem — 60 adam-gün)

| Grup | Adet |
| --- | --- |
| Silah ateşi (38 silah × 3 mesafe katmanı) | 114 |
| Silah mekanik (şarjör, kurma, kuru tetik) | 76 |
| Araç (motor idle/hız/frenleme, palet, taret, top) | 48 |
| Karakter (ayak sesi × 6 zemin, nefes, acı, ölüm) | 42 |
| Çevre döngüsü (6 biyom × 2 katman) | 12 |
| UI (18) + capture/hedef bildirim (10) | 28 |

---

## Öncelik Sırası (üretim dalgaları)

| Dalga | Kapsam | Hedef |
| --- | --- | --- |
| **D1 — Dikey dilim** | 1 harita (Bocage), 2 millet, 8 silah, 2 araç, çekirdek VFX/UI | Stil onayı + performans kanıtı |
| **D2 — Çekirdek içerik** | 4 harita, 4 millet, 24 silah, 10 araç | Kapalı beta |
| **D3 — Tam lansman** | 12 harita, 5 millet, 38 silah, 22 araç, editör kütüphanesi | Yayın |
| **D4 — Yaşayan oyun** | 6 haftada 1 harita + sezonluk kozmetik | Lansman sonrası |

Dikey dilim onaylanmadan D2'ye geçilmez. Stil onayı, poligon bütçesi ve hedef cihaz FPS'i **aynı anda** sağlanmalıdır.
