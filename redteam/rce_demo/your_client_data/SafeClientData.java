import java.io.*; import java.util.*;
public class SafeClientData {
    public static Map<String,Object> fromByteArray(byte[] bytes) throws Exception {
        Map<String,Object> map = new HashMap<>();
        ByteArrayInputStream bis = new ByteArrayInputStream(bytes);
        ObjectInputStream in = new ObjectInputStream(bis);
        // бе­лый список: разрешаем только примитивы/строки, всё прочее — отказ
        in.setObjectInputFilter(info -> {
            Class<?> c = info.serialClass();
            if (c == null) return ObjectInputFilter.Status.ALLOWED;
            String nm = c.getName();
            if (nm.equals("java.lang.String") || nm.startsWith("java.lang.")) 
                return ObjectInputFilter.Status.ALLOWED;
            return ObjectInputFilter.Status.REJECTED;
        });
        int n = in.readInt();
        while (n > 0) { String k=in.readUTF(); Object v=in.readObject(); map.put(k,v); n--; }
        in.close(); bis.close();
        return map;
    }
}
