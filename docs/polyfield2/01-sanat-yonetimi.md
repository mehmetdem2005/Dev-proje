# 01 — Polyfield 2 Sanat Yönetimi (Art Bible)

## Tek Cümlelik Sanat Yönü

> **Polyfield 2, 2. Dünya Savaşı'nı düz gölgeli düşük poligonlu bir diorama gibi gösterir: siluet okunur, renk anlam taşır, hiçbir piksel oyuncuyu yanıltmaz.**

Birinci oyunun "oyuncaksı ama ciddi" kimliği korunur. Gelişme detay çözünürlüğünde değil, **tutarlılık, ışık ve çeşitlilikte** aranır.

## Beş Kural

1. **Siluet önce gelir.** Bir asset 128×128 piksele küçültülüp siyaha boyandığında hâlâ ne olduğu anlaşılmalı. Anlaşılmıyorsa model yeniden yapılır, doku eklenmez.
2. **Doku değil renk.** Malzeme ayrımı vertex color ve tek bir palet atlası ile yapılır. Albedo dışında doku kullanımı istisnadır, kural değil.
3. **Düz gölgeleme + tek yönlü ışık.** Normal map yok, parlaklık haritası yok. Hacim, poligon normalleri ve sahne ışığıyla oluşur.
4. **Okunabilirlik oynanışa hizmet eder.** Oyuncu, düşman ve capture bölgesi çevrenin renk aralığının dışında kalır. Çevre doygunluğu düşük, karakter/hedef doygunluğu yüksektir.
5. **Modülerlik zorunludur.** Her çevre asset'i 1 m ızgaraya oturur; harita editörü kullanıcısı parçaları birbirine kilitleyebilmelidir.

## Renk Sistemi

### Ana palet (paylaşılan atlas)

Tek bir 512×512 `palette_master.png` atlası; her malzeme atlasın bir hücresine UV'lenir. Bu atlas tüm çevre ve araç asset'leri tarafından paylaşılır → tek materyal, tek draw call ailesi.

| Rol | Hex | Kullanım |
| --- | --- | --- |
| Toprak / kuru | `#8A7B5C` | Yol, kazılmış siper, çamur |
| Çim / açık | `#7FA05A` | Tarla, kırlık |
| Çim / koyu | `#4F6B3C` | Ağaç tepesi, çalı |
| Kaya | `#8C8C88` | Kayalık, moloz |
| Beton | `#B9B6AC` | Bunker, kaldırım |
| Ahşap açık | `#C8A374` | Sandık, çit, iskele |
| Ahşap koyu | `#6E4F32` | Kiriş, gövde |
| Metal / pas | `#7A4A34` | Dikenli tel, hurda |
| Su | `#4E7E93` | Deniz, nehir, birikinti |
| Kar | `#E8ECF0` | Doğu Cephesi biyomu |
| Kum | `#D6C08A` | Kuzey Afrika biyomu |

### Millet renkleri (cephe kimliği)

Cephe tutarsızlığı Polyfield 1'in en somut görsel borcu. Polyfield 2'de her millet **kilitli bir kit** ile gelir: siluet + palet + ekipman. Karışım yok.

| Millet | Ana ton | Vurgu | Siluet imzası |
| --- | --- | --- | --- |
| ABD | `#5C6B4A` zeytin yeşili | `#C9A227` | Yuvarlak M1 kaskı, yüksek sırt çantası |
| Almanya | `#4A4F4A` sahra grisi | `#8C2F2F` | Çelik kask siperliği, yan mataralar |
| SSCB | `#6B6244` haki-kahve | `#A32323` | Pilotka/kulaklıklı şapka, geniş omuz hattı |
| İngiltere | `#6E6A4F` kaki | `#2F4E8C` | Yassı Brodie kaskı, geniş oval siluet |

**Takım ayrımı (dostluk okunabilirliği):** millet renkleri temadır, takım ayrımı değildir. Ayrım, karakter üzerinde **kol bandı + isim etiketi rengi** ile yapılır: dost `#3FA9F5`, düşman `#F5533F`. Bu iki renk çevre paletinde **hiçbir yerde kullanılmaz** — renkler oyun boyunca rezervedir.

### Renk körlüğü

Kırmızı/mavi ayrımı tek başına yeterli değildir. Ayarlar menüsünde üç mod: `Kırmızı-Mavi` (varsayılan), `Turuncu-Mor`, `Sarı-Mavi`. Ek olarak düşman etiketlerinde daima bir ▲ ikonu, dost etiketlerinde ● ikonu bulunur — şekil ayrımı renkten bağımsız çalışır.

## Işık ve Atmosfer

- **Tek yönlü ışık (directional)** + tek ambient renk. Nokta ışık sadece iç mekân ve el bombası patlamalarında, kare başına en fazla 4 adet.
- **Gölge:** yalnızca ana yönlü ışıktan, tek kademe cascade, 1024 px (Yüksek/Ultra), Orta'da 512 px, Düşük'te gölge kapalı + kontakt blob gölge.
- **Sis:** her biyomun kendi mesafe sisi rengi vardır; sis hem atmosfer hem de görüş mesafesi bütçesidir (bkz. `02-dunya-tasarimi.md`).
- **Gün döngüsü yok.** Her harita sabit, elle ayarlanmış bir ışık senaryosuna sahiptir (sabah / öğle / altın saat / fırtına). Dinamik gün döngüsü mobilde maliyet-fayda açısından reddedildi; bunun yerine aynı harita farklı ışık varyantlarıyla sunulur.

## Kamera ve Çerçeveleme

- FOV varsayılan 75°, ayarlanabilir 65–95°.
- Silah modeli ekranın sağ alt üçte birinde; nişan alırken (ADS) FOV 55°'ye iner.
- Balıkgözü lens efekti Polyfield 1'den devralınır, opsiyonel kalır.

## VFX Dili

Efektler de düşük poligon mantığına uyar: **partikül değil, kart ve mesh tabanlı, sert kenarlı, kademeli.**

| Efekt | Yaklaşım |
| --- | --- |
| Patlama | 3 kademeli mesh küre + halka dalgası, sert renk geçişi (turuncu → gri) |
| Namlu ateşi | 2 kare flipbook, 60 ms |
| Toz / moloz | Düşük poligonlu küp partikülleri, yerçekimli, 1.5 s ömür |
| Mermi izi | Tek quad şerit, sadece 5. mermide bir (görsel gürültü kontrolü) |
| Kan / isabet | Kırmızı poligon çıkıntı + isabet ikonu; kan seviyesi ayarlanabilir |
| Sis / duman | Düşük çözünürlüklü yumuşak kart (soft particle), maks. 32 aktif |
| Su sıçraması | Mesh koni + halka |

**Bütçe:** aynı anda ekranda maks. 400 partikül (Düşük), 1200 (Ultra). Overdraw, mobilde kare düşüşünün bir numaralı sebebidir — her efekt için ekran kaplama alanı ölçülür ve gözden geçirilir.

## UI / HUD İlkeleri

- HUD, oyun dünyasının rengini kullanmaz — nötr beyaz `#F2F2F0` ve %60 opak koyu `#14171A` panel.
- Capture bölge göstergeleri ekranın üst şeridinde, 5 bölge = 5 sabit rozet (A–E).
- Ateş/nişan/çömelme butonları başparmak erişim yayında; boyutları ve konumları oyuncu tarafından düzenlenebilir (Polyfield 1'in "revamped UI" çizgisinin devamı).
- Yazı tipi: tek geometrik sans (ör. Barlow / Inter), 3 ağırlık. Dekoratif savaş temalı font kullanılmaz — okunabilirlik kazanır.

## Reddedilenler (kapsam dışı)

Bu maddeler bilinçli olarak dışarıda bırakılmıştır; tekrar gündeme gelirse buradan referans verin.

- PBR malzeme akışı, normal/roughness haritaları
- Dinamik gün-gece döngüsü ve gerçek zamanlı hava sistemi
- Karakter yüz animasyonu, bezyapı (cloth) simülasyonu
- Işın izleme, ekran uzayı yansıma, SSAO (Ultra'da hafif SSAO opsiyonel değerlendirilebilir)
- Fotogerçekçi doku çözünürlüğü (2K+ karakter dokusu)
