# Yayınlanan APK'lar

Bu klasör **sürümlenmiş** APK'ları taşır — her yapı değil. GitHub Release
oluşturma bu depoda kullanılamadığı için binary'ler doğrudan depoda tutuluyor;
her dosya git geçmişinde kalıcıdır, o yüzden buraya sadece paylaşılacak sürümler
konur. Günlük yapılar `../build/` altında kalır ve gitignore'dadır.

| Dosya | Sürüm | Boyut | SHA-256 |
| --- | --- | --- | --- |
| `polyfield2-ridgeline-v0.6.0.apk` | 0.6.0 (code 6) | 62 MB | `6aa0f6b833ec0d0ff01b2bb5ac80a1f2be182939f2498695d35beee0d6b58310` |

Yalnızca en son sürüm tutulur — her binary git geçmişinde kalıcı olduğu için
eskiler siliniyor.

## Kurulum

Telefona indirin ve açın. Android "bilinmeyen kaynaklardan yükleme" izni
isteyecektir.

| | |
| --- | --- |
| Paket | `com.mehmetdem.polyfield2` |
| ABI | arm64-v8a (64-bit ARM; x86 emülatörde çalışmaz) |
| Target SDK | 36 |
| Renderer | Vulkan, Forward Mobile |
| İzinler | VIBRATE, WAKE_LOCK — ağ ve depolama izni yok |

Debug anahtarıyla imzalıdır: sideload ve test için uygundur, Play Store yükleme
anahtarı olarak kullanılamaz.

## Doğrulama

```bash
sha256sum -c SHA256SUMS.txt
```

## Yeniden üretme

```bash
export ANDROID_SDK_ROOT=/path/to/android-sdk
export GODOT_ANDROID_KEYSTORE=/path/to/debug.keystore
../tools/export_apk.sh
```
