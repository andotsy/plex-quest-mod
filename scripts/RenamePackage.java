import com.reandroid.apk.ApkModule;
import com.reandroid.arsc.chunk.PackageBlock;
import com.reandroid.arsc.chunk.xml.AndroidManifestBlock;
import com.reandroid.arsc.item.ResXmlString;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;

/** Change installation identity without recompiling layouts or changing resource IDs. */
class RenamePackage {
    private static final String ORIGINAL = "com.plexapp.android";
    private static final String TARGET = "com.plexapp.android.tv";

    public static void main(String[] args) throws Exception {
        if (args.length != 3) {
            throw new IllegalArgumentException("Usage: RenamePackage input.apk output.apk report.json");
        }
        int references = 0;
        try (ApkModule apk = ApkModule.loadApkFile(new File(args[0]))) {
            apk.setLoadDefaultFramework(false);
            String original = apk.getPackageName();
            if (!ORIGINAL.equals(original) && !TARGET.equals(original)) {
                throw new IllegalArgumentException("Unsupported package: " + original);
            }
            if (apk.getVersionCode() != 971050399) {
                throw new IllegalArgumentException("Unsupported Plex version code.");
            }
            AndroidManifestBlock manifest = apk.getAndroidManifest();
            // Providers, custom permissions, and launcher aliases share package-prefixed
            // strings. Their values must change together to permit side-by-side installs.
            for (ResXmlString item : manifest.getStringPool()) {
                String value = item.get();
                if (value != null && (value.equals(ORIGINAL) || value.startsWith(ORIGINAL + "."))
                        && !value.equals(TARGET) && !value.startsWith(TARGET + ".")) {
                    item.set(TARGET + value.substring(ORIGINAL.length()));
                    references++;
                }
            }
            apk.setPackageName(TARGET);
            for (PackageBlock resourcePackage : apk.getTableBlock().listPackages()) {
                if (resourcePackage.getId() == 0x7f) {
                    resourcePackage.setName(TARGET);
                }
            }
            apk.refreshManifest();
            apk.refreshTable();
            apk.setApkSignatureBlock(null);
            for (var entry : apk.getInputSources()) {
                String name = entry.getAlias();
                if (name.startsWith("META-INF/") &&
                        (name.equals("META-INF/MANIFEST.MF") || name.endsWith(".SF")
                        || name.endsWith(".RSA") || name.endsWith(".DSA") || name.endsWith(".EC"))) {
                    apk.removeInputSource(name);
                }
            }
            apk.writeApk(new File(args[1]));
        }
        try (ApkModule verified = ApkModule.loadApkFile(new File(args[1]))) {
            verified.setLoadDefaultFramework(false);
            if (!TARGET.equals(verified.getPackageName())) {
                throw new IllegalStateException("Output package ID did not change.");
            }
            for (ResXmlString item : verified.getAndroidManifest().getStringPool()) {
                String value = item.get();
                if (value != null && (value.equals(ORIGINAL) || value.startsWith(ORIGINAL + "."))
                        && !value.equals(TARGET) && !value.startsWith(TARGET + ".")) {
                    throw new IllegalStateException("Unrenamed manifest reference: " + value);
                }
            }
            for (PackageBlock resourcePackage : verified.getTableBlock().listPackages()) {
                if (resourcePackage.getId() == 0x7f && !TARGET.equals(resourcePackage.getName())) {
                    throw new IllegalStateException("Resource package ID did not change.");
                }
            }
        }
        Files.writeString(Path.of(args[2]), "{\"package_id\":\"" + TARGET
                + "\",\"renamed_manifest_strings\":" + references + "}\n");
        System.out.println("Verified standalone package identity: " + TARGET);
    }
}
