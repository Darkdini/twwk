import java.io.*; import java.net.*; import java.util.*;
// Защищённый сервер — белый список классов: всё, что не разрешено явно, отвергается
// ДО создания объекта, поэтому readObject "злого" класса не успевает выполниться.
public class SafeServer {
    static final Set<String> ALLOW = new HashSet<>(Arrays.asList(
        "java.lang.String","java.lang.Integer","java.lang.Number"));
    public static void main(String[] a) throws Exception {
        ServerSocket ss = new ServerSocket(9971);
        System.out.println("[SAFE] слушаю 9971, белый список классов десериализации");
        Socket s = ss.accept();
        ObjectInputStream in = new ObjectInputStream(s.getInputStream()) {
            protected Class<?> resolveClass(ObjectStreamClass d) throws IOException, ClassNotFoundException {
                if (!ALLOW.contains(d.getName()))
                    throw new InvalidClassException("заблокирован недопустимый класс: " + d.getName());
                return super.resolveClass(d);
            }
        };
        try { Object o = in.readObject(); System.out.println("[SAFE] ок: " + o); }
        catch (Exception e) { System.out.println("[SAFE] ОТКЛОНЕНО -> " + e.getMessage()); }
        s.close(); ss.close();
    }
}
