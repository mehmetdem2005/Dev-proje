# 00 — Polyfield 1 Görsel ve İçerik Araştırması

Bu doküman, Polyfield 2'nin sanat yönü ve asset planı için temel aldığımız **mevcut oyunun (Polyfield, v0.7.5)** kamuya açık kaynaklardan derlenmiş durum tespitidir. Tüm veriler mağaza sayfaları, resmî site, topluluk wiki'leri ve inceleme yazılarından toplanmıştır — APK tersine mühendisliği yapılmamıştır.

## Künye

| Alan | Değer |
| --- | --- |
| Oyun | Polyfield (Polyfield WW2) |
| Geliştirici | Mohammad Alizadeh |
| Paket adı | `com.MA.Polyfield` |
| Sürüm | 0.7.5 (Haziran 2026) |
| Platform | Android 7.0+, iOS |
| Boyut | ~257 MB (APK), ~393 MB (iOS) |
| Tür | Stilize düşük poligonlu (low-poly) 2. Dünya Savaşı FPS |
| Puan | 8.7 / 10 (APKPure), genel olarak olumlu |

## Oyun Yapısı

- **Territory Control** ana mod: 5 bölgenin ele geçirilmesi ve elde tutulması. Bölgeyi elde tuttukça puan kazanılıyor.
- **32v32** takım savaşları (maç başına 64 oyuncu), sunucu tarafında aynı anda **128 oyuncuya** kadar kapasite.
- **Offline bot maçları** — internet olmadan AI'ya karşı oynanabiliyor; botlar tank da spawn edebiliyor.
- **Oyun içi harita editörü** — arazi şekillendirme, obje yerleştirme, capture bölgesi tanımlama, kaydetme ve paylaşma.
- **Topluluk haritaları** — indirilebiliyor; toplulukta `pf-tool` gibi üçüncü parti harita paylaşım araçları oluşmuş durumda.
- **Sınıflar** — 0.7 ile Tanker ve Scout sınıfları geldi.
- **Liderlik tabloları** ve arkadaşlarla oturum kurma.

## İçerik Envanteri (0.7.x itibarıyla)

**Haritalar (~22 adet):** Normandy (temel harita), Omaha Beach D-DAY, Fort Verdun, OpenField, Poly_Bay, Baronstadt ve diğerleri.

**Silahlar:** Thompson M1A1, M3 Grease Gun, STEN, BAR-1918A2, MG-42, MP-507, Walther P38, Welrod (susturuculu tabanca), Bazooka, Panzerfaust.

**Araçlar:** Jagdpanther, Sherman Firefly. Araç çeşitliliği oyunun en sık eleştirilen eksiği.

**Teknik özellikler:** Kademeli grafik ayarları (Ultra dahil), yıkım fiziği (0.7), yenilenen ağ çözümü (0.7), editörde duman partikülleri ve "analyzer" aracı (0.7.5), Ultra'da yüksek çözünürlüklü dürbün, desteklenen cihazlarda balıkgözü lens efekti.

## Görsel Dil — Tespitler

1. **Flat-shaded low-poly.** Karakterler, silahlar ve çevre basit geometrik formlar ve temiz hatlarla modellenmiş. Normal map ve yüksek frekanslı doku detayı neredeyse yok.
2. **Renk ile okunabilirlik.** Doku yerine renk paletiyle malzeme ayrımı yapılıyor — vertex color / atlas tabanlı bir yaklaşım.
3. **Ton kontrastı.** WW2 gibi ağır bir temaya rağmen görsel dil "oyuncaksı" ve yaklaşılabilir. Bu kontrast oyunun kimliği; Polyfield 2'de korunmalı.
4. **Siluet önceliği.** Mobil ekranda 50–150 m mesafeden düşman ayırt edilebiliyor; bu, düşük poligonda kalın ve ayrık silüetlerle sağlanmış.
5. **Cephe/millet ayrımı zayıf.** İncelemelerde "faction inconsistency" (aynı takımda karışık üniforma/ekipman) şikâyeti var — Polyfield 2'nin düzeltmesi gereken somut bir görsel borç.

## Zayıf Noktalar → Polyfield 2 Fırsatları

| Polyfield 1 eksiği | Polyfield 2 hedefi |
| --- | --- |
| Sınırlı silah çeşitliliği | Millet bazlı tam silah ağacı (bkz. `03-asset-listesi.md`) |
| 2 araç | Hafif/orta/ağır tank, yarı paletli, jeep, uçaksavar, top |
| Cephe tutarsızlığı | Kilitli millet kiti: siluet + palet + ekipman seti |
| Düşük cihazlarda FPS düşüşü | Katı poligon/draw-call bütçesi ve 4 kademeli kalite profili |
| Tek biyom hissi (Normandiya ağırlıklı) | 6 biyom: Normandiya, Doğu Cephesi kışı, Kuzey Afrika, Pasifik, Kent yıkıntısı, Alp |
| Editörde sınırlı prop kütüphanesi | Kategorize, etiketli, ~600 parçalık modüler kit |
| Görsel efektler sade | Stilize VFX seti (patlama, toz, sis, iz, hasar) |

## Fikrî Mülkiyet Notu

Görev orijinal firmadan geldiği için Polyfield 2, birinci oyunun devamı niteliğindedir. Buna rağmen üretim kuralımız net:

- Polyfield 1'in **kaynak dosyaları (FBX/PSD/Unity projesi) firmadan resmî olarak devralınmadıkça**, hiçbir asset APK/IPA içinden çıkarılıp kullanılmaz.
- Tüm modeller, dokular ve sesler bu dokümandaki stil rehberine göre **sıfırdan üretilir**.
- Gerçek tarihî araç ve silah isimleri kullanılabilir (tarihî gerçekler telifli değildir), ancak üçüncü parti asset paketlerinin (ör. hazır ticari WW2 kitleri) lisans şartları ayrıca doğrulanır.

## Kaynaklar

- [Polyfield — Google Play](https://play.google.com/store/apps/details?id=com.MA.Polyfield&hl=en_US)
- [Polyfield — App Store](https://apps.apple.com/us/app/polyfield/id6708235511)
- [polyfield.net — resmî site](https://polyfield.net/)
- [Polyfield — APKPure sürüm geçmişi](https://apkpure.com/polyfield/com.MA.Polyfield)
- [Polyfield Encyclopedia Wiki — Official Maps](https://polyfield-encyclopedia.fandom.com/wiki/Official_Maps)
- [Polyfield Android & iOS Review — Trendz Beta Games](https://www.trendzbetagames.com/2026/06/polyfield-android-ios-review-hidden-gem-ww2-shooter.html)
- [Polyfield — Softonic](https://polyfield.en.softonic.com/android)
- [aliernfrog/pf-tool — topluluk harita paylaşım aracı](https://github.com/aliernfrog/pf-tool)
