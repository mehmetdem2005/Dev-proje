# Polyfield 2 — Görsel Yön ve Asset Planı

Bu klasör, **Polyfield 2**'nin sanat yönü, dünya tasarımı ve asset üretim planını içerir. Plan, orijinal Polyfield'ın (v0.7.5, Mohammad Alizadeh) kamuya açık kaynaklardan yapılmış görsel ve içerik analizine dayanır.

## Dokümanlar

| # | Doküman | İçerik |
| --- | --- | --- |
| 00 | [Polyfield 1 Araştırması](00-arastirma-polyfield-1.md) | Orijinal oyunun künyesi, içerik envanteri, görsel dil tespitleri, zayıf noktalar |
| 01 | [Sanat Yönetimi](01-sanat-yonetimi.md) | Stil rehberi, renk sistemi, ışık, VFX dili, UI ilkeleri, kapsam dışı kararlar |
| 02 | [Dünya Tasarımı](02-dunya-tasarimi.md) | 6 biyom, 12 lansman haritası, harita iskeleti, arazi sistemi, yıkılabilirlik, editör |
| 03 | [Asset Listesi](03-asset-listesi.md) | ~1100 kalemlik envanter, poligon bütçeleri, üretim dalgaları |
| 04 | [Teknik Bütçe ve Pipeline](04-teknik-butce-pipeline.md) | Cihaz matrisi, kare bütçesi, doku stratejisi, kabul kontrol listesi, araç zinciri |
| 05 | [Yol Haritası](05-yol-haritasi.md) | Ekip, 36 haftalık takvim, kritik yol, riskler, başarı ölçütleri |

## Tek Sayfalık Özet

**Sanat yönü:** Düz gölgeli düşük poligon korunur. Gelişme detay çözünürlüğünde değil; **tutarlılık, biyom çeşitliliği, ışık ve performans** eksenindedir.

**Polyfield 1'in dört somut borcu ve karşılıkları:**

| Borç | Karşılık |
| --- | --- |
| Cephe görsel tutarsızlığı | Kilitli millet kiti — karışım yapısal olarak imkânsız |
| 2 araç, ~10 silah | 22 araç, 38 ateşli silah, millet bazlı silah ağacı |
| Düşük cihazlarda kare düşüşü | Katı kare bütçesi + gecelik cihaz farmı regresyon testi |
| Tek biyom hissi | 6 biyom, editörde tek tıkla tema değişimi |

**Ölçek:** 6 biyom · 12 lansman haritası · 5 millet · 38 silah · 22 araç · ~1100 asset · ~735 adam-gün · ~36 hafta.

**Değişmez kurallar:**
1. Siluet 128 px'te okunmalı.
2. Doku değil renk — tek paylaşılan palet atlası, normal map yok.
3. Tüm modüler çevre 1 m ızgaraya oturur.
4. Karakter rig'i F0'da kilitlenir, sonra dokunulmaz.
5. Dikey dilim, düşük profil cihazda 30 FPS'i tutturmadan F2'ye geçilmez.

## Fikrî Mülkiyet

Polyfield 1'in kaynak dosyaları firmadan resmî olarak devralınmadıkça, hiçbir asset dağıtılmış paketlerden çıkarılıp kullanılmaz. Tüm modeller, dokular ve sesler bu klasördeki stil rehberine göre sıfırdan üretilir. Ayrıntı: [00-arastirma-polyfield-1.md](00-arastirma-polyfield-1.md#fikrî-mülkiyet-notu)
