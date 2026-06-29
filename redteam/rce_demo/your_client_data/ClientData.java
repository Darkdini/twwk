import java.io.*; import java.util.*;
public class ClientData {
    // 1:1 повтор логики J0/g.java: readInt, затем readUTF+readObject в цикле
    public static Map<String,Object> fromByteArray(byte[] bytes) throws Exception {
        Map<String,Object> map = new HashMap<>();
        if (bytes.length > 10240) throw new IOException("too big"); // твой лимит 10240
        ByteArrayInputStream bis = new ByteArrayInputStream(bytes);
        ObjectInputStream in = new ObjectInputStream(bis);
        int n = in.readInt();
        while (n > 0) {
            String key = in.readUTF();
            Object val = in.readObject();   // <<< РОВНО ЗДЕСЬ выполняется чужой код
            map.put(key, val);
            n--;
        }
        in.close(); bis.close();
        return map;
    }
}
