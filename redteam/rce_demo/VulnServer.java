import java.io.*; import java.net.*;
// Уязвимый сервер — делает РОВНО то, на что я указывал в твоём коде: readObject() из сети.
public class VulnServer {
    public static void main(String[] a) throws Exception {
        ServerSocket ss = new ServerSocket(9970);
        System.out.println("[VULN] слушаю 9970, читаю клиента через ObjectInputStream.readObject()");
        Socket s = ss.accept();
        ObjectInputStream in = new ObjectInputStream(s.getInputStream());
        System.out.println("[VULN] пришли данные от клиента, десериализую...");
        Object o = in.readObject();   // <<< здесь выполняется чужой код
        System.out.println("[VULN] readObject вернул объект класса: " + o.getClass().getName());
        s.close(); ss.close();
    }
}
