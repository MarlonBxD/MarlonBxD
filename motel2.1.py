import os
import csv
import time
import math 
from datetime import datetime,timedelta, time as dt_time
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from collections import defaultdict
from email.mime.application import MIMEApplication
from email import encoders
from email.mime.base import MIMEBase
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import sqlite3
import re
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from cryptography.fernet import Fernet
import pytz
from datetime import datetime

inventario = {}
tarifa_por_hora = 10

class Usuario:
    def __init__(self, nombre, contrasena, permisos):
        self.nombre = nombre
        self.contrasena = contrasena
        self.permisos = permisos

class Habitacion:
    def __init__(self, numero):
        self.numero = numero 
        self.tiempo_ocupacion = 0
        self.productos = {}
        self.ocupada = False
        self.start_time = None
        self.historial = []
        self.placa_vehiculo = ""

    def iniciar(self):
        self.ocupada = True
        self.start_time = time.time()

    def get_tiempo_ocupacion(self):
        if self.ocupada:
            elapsed_time = int(time.time() - self.start_time)
            horas, rem = divmod(elapsed_time, 3600)
            minutos, segundos = divmod(rem, 60)
            return f"{horas:02d}:{minutos:02d}:{segundos:02d}"
        return "00:00:00"


    def agregar_producto(self, producto, cantidad):
        if producto.nombre in self.productos:
            self.productos[producto.nombre] += cantidad
        else:
            self.productos[producto.nombre] = cantidad
        producto.vender(cantidad)


    def calcular_total(self, tarifa_por_hora):
        elapsed_time = time.time() - self.start_time
        
        # Si el tiempo es menor a 5 minutos, no se cobra nada
        if elapsed_time < 300:
            return 0

        # Convertir el tiempo transcurrido a horas
        horas = elapsed_time / 3600
        total_productos = sum(inventario[producto].precio * cantidad for producto, cantidad in self.productos.items())

        if self.ocupada:
            if self.numero == 7:
                # Primera hora cobra 15000
                if horas <= 1:
                    return 15000 + total_productos
                else:
                    # Horas adicionales después de la primera
                    minutos_adicionales = (horas - 1) * 60
                    cuartos_hora_adicionales = minutos_adicionales // 15
                    return 15000 + cuartos_hora_adicionales * 3000 + total_productos
            else:
                # Primera hora cobra 12000
                if horas <= 1:
                    return 12000 + total_productos
                else:
                    # Horas adicionales después de la primera
                    minutos_adicionales = (horas - 1) * 60
                    cuartos_hora_adicionales = minutos_adicionales // 15
                    return 12000 + cuartos_hora_adicionales * 3000 + total_productos

        return 0

    def reiniciar(self):
        if self.ocupada:
            total = self.calcular_total(tarifa_por_hora)
            ocupacion = {
                "tiempo": time.time() - self.start_time,
                "productos": self.productos.copy(),
                "total": total
            }
            self.historial.append(ocupacion)
        self.tiempo_ocupacion = 0
        self.productos = {}
        self.ocupada = False
        self.start_time = None

class Producto:
    def __init__(self, nombre, precio, existencia=0):
        self.nombre = nombre
        self.precio = precio
        self.existencia = existencia

    def vender(self, cantidad):
        self.existencia -= cantidad
    

class MotelApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Motel App")
        self.cargar_inventario_desde_csv()   
        
        #self.placa_vehiculo = None

        self.habitaciones = [Habitacion(i) for i in range(1, 10)]
        self.placa_actual = None

        self.usuarios = [
            Usuario("admin", "admin", ["iniciar", "agregar_producto", "cobrar", "gestionar_inventario", "ver_historial", "gestionar_usuarios"]),
            Usuario("usuario", "usuario", ["iniciar", "agregar_producto", "cobrar"])
        ]
        self.usuario_actual = None
    

        self.crear_interfaz_inicio_sesion()
        self.connect_to_database()

    # Función para cargar el inventario desde un archivo CSV
    def cargar_inventario_desde_csv(self):
            
        self.archivo_csv = "inventario.csv"
        try:
            with open(self.archivo_csv, mode='r', newline='') as file:
                reader = csv.reader(file)
                next(reader)  # Saltar encabezado
                for row in reader:
                    nombre = row[0]
                    precio = float(row[1])
                    existencia = int(row[2])
                    inventario[nombre] = Producto(nombre, precio, existencia)
        except FileNotFoundError:
            messagebox.showwarning("Advertencia", f"No se encontró el archivo {self.archivo_csv}. Se creará uno nuevo al guardar.")
        return inventario

    # Función para guardar el inventario en un archivo CSV
    def guardar_inventario_csv(self):
        archivo_csv = "inventario.csv"
        try:
            with open(archivo_csv, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["Producto", "Precio", "Existencia"])
                for producto in inventario.values():
                    writer.writerow([producto.nombre, producto.precio, producto.existencia])
            messagebox.showinfo("Éxito", f"Inventario guardado en {archivo_csv} correctamente.")
        except IOError:
            messagebox.showerror("Error", f"No se pudo guardar el archivo {archivo_csv}.")

    def connect_to_database(self):
        db_path = 'motel.db'
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS transacciones (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                habitacion_numero INTEGER,
                                placa_vehiculo TEXT,
                                tiempo_ocupacion REAL,
                                producto_nombre TEXT,
                                total REAL,
                                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        self.conn.commit()

    def crear_interfaz_inicio_sesion(self):
        self.frame_inicio_sesion = tk.Frame(self.root)
        self.frame_inicio_sesion.pack(padx=10, pady=10)
        self.frame_inicio_sesion.config(bg="lightblue")

        tk.Label(self.frame_inicio_sesion, text=(f"INICIO DE SESION \n MOTEL LA FORTUNA"),bg="lightblue", font=("Arial", 25, "bold")).grid(row=0, columnspan=2, pady=10)
        
        tk.Label(self.frame_inicio_sesion, text="Usuario:",bg="lightblue").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.entry_usuario = tk.Entry(self.frame_inicio_sesion)
        self.entry_usuario.grid(row=1, column=1, padx=5, pady=5)

        tk.Label(self.frame_inicio_sesion, text="Contraseña:",bg="lightblue").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.entry_contrasena = tk.Entry(self.frame_inicio_sesion, show="*")
        self.entry_contrasena.grid(row=2, column=1, padx=5, pady=5)

        btn_iniciar_sesion = tk.Button(self.frame_inicio_sesion, text="Iniciar Sesión", command=self.iniciar_sesion, width=15)
        btn_iniciar_sesion.grid(row=3, columnspan=2, pady=10)

    def enviar_reporte(self, destinatario_email):
        transacciones = self.transacciones_cierre_caja  # Usar las transacciones almacenadas
        print("Transacciones obtenidas:", transacciones)  # Depuración

        # Filtrar transacciones válidas y convertir a float
        transacciones_validas = []
        for transaccion in transacciones:
            try:
                transaccion_total = float(transaccion[3])  # total es el cuarto elemento en la tupla
                transacciones_validas.append((transaccion[0], transaccion[1], transaccion[2], transaccion_total, transaccion[4]))
            except ValueError:
                print(f"Transacción con valor total inválido: {transaccion[3]}")

        total_diario = sum(transaccion[3] for transaccion in transacciones_validas)

        # Crear un PDF con el reporte diario
        pdf = canvas.Canvas("reporte.pdf", pagesize=letter)
        pdf.setFont("Helvetica", 12)
        pdf.drawString(100, 750, "Reporte diario de transacciones")
        pdf.drawString(100, 725, f"Fecha: {time.strftime('%Y-%m-%d')}")
        pdf.drawString(100, 700, f"Total diario: ${total_diario:.2f}")
        pdf.drawString(100, 675, "Transacciones:")

        for i, transaccion in enumerate(transacciones_validas):
            habitacion_numero, placa_vehiculo, producto_nombre, total, fecha = transaccion
            producto_str = producto_nombre if producto_nombre else "N/A"
            pdf.drawString(100, 650 - i * 25, f"Habitación {habitacion_numero} - Placa {placa_vehiculo} - Producto {producto_str} - ${total:.2f} - {fecha}")

        pdf.save()

        # Guardar las transacciones en un archivo CSV
        with open('reporte_diario.csv', 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            for transaccion in transacciones_validas:
                writer.writerow(transaccion)

        # Configurar el correo electrónico
        remitente = "motellafortuna6@gmail.com"
        password = "czxn kbiq fpjt foqe"  # Utiliza una contraseña de aplicación generada en tu cuenta de Google
        asunto = "Reporte diario de transacciones"
        cuerpo = f"Adjunto el reporte diario de transacciones del día {time.strftime('%Y-%m-%d')}."

        # Crear el mensaje
        mensaje = MIMEMultipart()
        mensaje['From'] = remitente
        mensaje['To'] = destinatario_email
        mensaje['Subject'] = asunto
        mensaje.attach(MIMEText(cuerpo, 'plain'))

        # Adjuntar el PDF
        with open("reporte.pdf", "rb") as adjunto:
            parte = MIMEBase('application', 'octet-stream')
            parte.set_payload(adjunto.read())
            encoders.encode_base64(parte)
            parte.add_header('Content-Disposition', f"attachment; filename= reporte.pdf")
            mensaje.attach(parte)

        # Enviar el correo
        try:
            servidor = smtplib.SMTP('smtp.gmail.com', 587)
            servidor.starttls()
            servidor.login(remitente, password)
            texto = mensaje.as_string()
            servidor.sendmail(remitente, destinatario_email, texto)
            servidor.quit()
            print("Correo enviado exitosamente.")
        except Exception as e:
            print(f"Error al enviar el correo: {str(e)}")



    def abrir_cierre_caja(self):
        ahora = datetime.now()

        if ahora.time() >= dt_time(6, 0) and ahora.time() < dt_time(18, 0):
            # Turno de 06:00 A.M. a 06:00 P.M.
            inicio_turno = ahora.replace(hour=6, minute=0, second=0, microsecond=0)
            fin_turno = ahora.replace(hour=18, minute=0, second=0, microsecond=0)
        else:
            # Turno de 06:00 P.M. a 06:00 A.M. (del día siguiente)
            if ahora.time() >= dt_time(18, 0):
                inicio_turno = ahora.replace(hour=18, minute=0, second=0, microsecond=0)
                fin_turno = (ahora + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
            else:
                inicio_turno = (ahora - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
                fin_turno = ahora.replace(hour=6, minute=0, second=0, microsecond=0)

        self.cursor.execute('''SELECT habitacion_numero, placa_vehiculo, producto_nombre, total, fecha
                            FROM transacciones 
                            WHERE fecha BETWEEN ? AND ?''', 
                            (inicio_turno, fin_turno))
        transacciones = self.cursor.fetchall()

        self.transacciones_cierre_caja = transacciones  # Almacenar las transacciones para uso posterior

        total_turno = sum(transaccion[3] for transaccion in transacciones)  # Sumar en base a la columna 'total'

        self.cierre_caja_window = tk.Toplevel(self.root)
        self.cierre_caja_window.title("Cierre de Caja")
        self.cierre_caja_window.geometry("700x400")

        tk.Label(self.cierre_caja_window, text=f"Turno: {inicio_turno.strftime('%Y-%m-%d %H:%M:%S')} - {fin_turno.strftime('%Y-%m-%d %H:%M:%S')}", font=("Helvetica", 14, "bold")).pack(pady=10)
        tk.Label(self.cierre_caja_window, text=f"Total del Turno: ${total_turno:.2f}", font=("Helvetica", 12, "bold")).pack(pady=10)

        # Crear Treeview para mostrar transacciones
        tree = ttk.Treeview(self.cierre_caja_window, columns=("Habitacion", "Placa", "Producto", "Total", "Fecha"), show="headings")
        tree.heading("Habitacion", text="Habitación")
        tree.heading("Placa", text="Placa del Vehículo")
        tree.heading("Producto", text="Producto")
        tree.heading("Total", text="Total")
        tree.heading("Fecha", text="Fecha")

        for transaccion in transacciones:
            habitacion_numero, placa_vehiculo, producto_nombre, total, fecha = transaccion
            tree.insert("", tk.END, values=(habitacion_numero, placa_vehiculo, producto_nombre or "N/A", total, fecha))

        tree.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        def cerrar_y_enviar_reporte():
            self.enviar_reporte("wilmarcifuentes728@gmail.com")
            self.cierre_caja_window.destroy()

        btn_cerrar = tk.Button(self.cierre_caja_window, text="Cerrar", command=cerrar_y_enviar_reporte)
        btn_cerrar.pack(pady=10, padx=10)


    def ver_ganancias_mensuales(self):
        self.frame_ganancias_mensuales = tk.Frame(self.root)
        self.frame_ganancias_mensuales.pack(padx=10, pady=10)
        self.frame_ganancias_mensuales.config(bg="lightblue")

        tk.Label(self.frame_ganancias_mensuales, text="GANANCIAS MENSUALES", bg="lightblue", font=("Arial", 12)).pack(pady=10)

        # Leer el archivo CSV de reportes diarios
        if not os.path.exists('reporte_diario.csv'):
            messagebox.showerror("Error", "No hay reportes diarios guardados")
            return

        ganancias_mensuales = defaultdict(float)
        with open('reporte_diario.csv', newline='') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                fecha = row[0]
                total = float(row[2])
                mes = fecha[:7]  # Obtener el mes en formato 'YYYY-MM'
                ganancias_mensuales[mes] += total

        # Mostrar las ganancias mensuales
        for mes, total in ganancias_mensuales.items():
            tk.Label(self.frame_ganancias_mensuales, text=f"Mes: {mes}, Total: ${total:.2f}", bg="lightblue").pack()

    def iniciar_sesion(self):
        nombre_usuario = self.entry_usuario.get()
        contrasena = self.entry_contrasena.get()

        for usuario in self.usuarios:
            if usuario.nombre == nombre_usuario and usuario.contrasena == contrasena:
                self.usuario_actual = usuario
                self.frame_inicio_sesion.pack_forget()
                self.crear_interfaz_principal()
                self.actualizar_tiempos()
                return

        messagebox.showerror("Error", "Usuario o contraseña incorrectos.")
    
    def cerrar_sesion(self):
        self.guardar_inventario_csv()
        for widget in self.root.winfo_children():
            widget.destroy()
        self.root.quit()
        self.conn.close()

    def crear_interfaz_principal(self):
        self.frame_principal = tk.Frame(self.root)
        self.frame_principal.pack(padx=10, pady=10)
        self.frame_principal.config(bg="lightblue")

        tk.Label(self.frame_principal, text="MOTEL LA FORTUNA", bg="lightblue", font=("Arial", 12)).pack(pady=10)

        tk.Button(self.frame_principal, text="INICIAR HABITACIÓN", command=self.iniciar_habitacion).pack(pady=10)
        tk.Button(self.frame_principal, text="AGREGAR PRODUCTO", command=self.agregar_producto).pack(pady=10)
        tk.Button(self.frame_principal, text="COBRAR", command=self.cobrar).pack(pady=10)
        tk.Button(self.frame_principal, text="GESTIONAR INVENTARIO", command=self.gestionar_inventario).pack(pady=10)
        tk.Button(self.frame_principal, text="VER HISTORIAL", command=self.ver_historial).pack(pady=10)
        tk.Button(self.frame_principal, text="GESTIONAR USUARIOS", command=self.gestionar_usuarios).pack(pady=10)
        tk.Button(self.frame_principal, text="GANANCIAS MENSUALES", command=self.ver_ganancias_mensuales).pack(pady=10)

    def crear_interfaz_principal(self):
        self.tabla_frame = ttk.Frame(self.root)
        self.tabla_frame.pack()

        # Configuración del Treeview con la columna de Placa después del Número
        self.tabla = ttk.Treeview(self.tabla_frame, columns=("Numero", "Placa", "Estado", "Tiempo", "Productos", "Cobrar"), show='headings')
        self.tabla.heading("Numero", text="Habitación")
        self.tabla.heading("Placa", text="Placa")  # Columna para la placa
        self.tabla.heading("Estado", text="Estado")
        self.tabla.heading("Tiempo", text="Tiempo")
        self.tabla.heading("Productos", text="Productos")
        self.tabla.heading("Cobrar", text="Cobrar")
        self.tabla.column("Numero", width=100)
        self.tabla.column("Placa", width=100)  # Ajustar ancho para la columna de placa
        self.tabla.column("Estado", width=100)
        self.tabla.column("Tiempo", width=150)
        self.tabla.column("Productos", width=150)
        self.tabla.column("Cobrar", width=100)

        style = ttk.Style()
        style.configure("Treeview", background="lightblue", foreground="black", fieldbackground="lightblue")
        style.map('Treeview', background=[('selected', 'blue')])

        self.tabla.grid(row=0, column=0, columnspan=7)  # Ajustar columnspan para incluir la nueva columna

        # Insertar habitaciones en el Treeview
        for habitacion in self.habitaciones:
            self.tabla.insert("", "end", iid=habitacion.numero, values=(habitacion.numero, "", "Libre", "0:00:00", "-", "-"))

        # Botones
        btn_iniciar = tk.Button(self.tabla_frame, text="Iniciar", command=self.iniciar_habitacion)
        btn_iniciar.grid(row=1, column=0, padx=5, pady=10)

        btn_agregar_producto = tk.Button(self.tabla_frame, text="Agregar Producto", command=self.abrir_agregar_producto)
        btn_agregar_producto.grid(row=1, column=1, padx=5, pady=10)

        btn_cobrar = tk.Button(self.tabla_frame, text="Cobrar", command=self.abrir_cobrar)
        btn_cobrar.grid(row=1, column=2, padx=5, pady=10)

        btn_historial = tk.Button(self.tabla_frame, text="Historial", command=self.abrir_historial)
        btn_historial.grid(row=1, column=3, padx=5, pady=10)

        btn_gestionar_inventario = tk.Button(self.tabla_frame, text="Gestionar Inventario", command=self.mostrar_interfaz_gestion_inventario)
        btn_gestionar_inventario.grid(row=1, column=4, padx=5, pady=10)

        btn_gestionar_usuarios = tk.Button(self.tabla_frame, text="Gestionar Usuarios", command=self.abrir_gestionar_usuarios)
        btn_gestionar_usuarios.grid(row=1, column=5, padx=5, pady=10)

        btn_cerrar_sesion = tk.Button(self.tabla_frame, text="Cerrar Sesión", command=self.cerrar_sesion)
        btn_cerrar_sesion.grid(row=1, column=6, padx=5, pady=10)

        btn_mover_habitacion = tk.Button(self.root, text="Mover Habitación", command=self.abrir_mover_habitacion)
        btn_mover_habitacion.pack(pady=10)

        btn_cierre_caja = tk.Button(self.root, text="Cierre de Caja", command=self.abrir_cierre_caja)
        btn_cierre_caja.pack(pady=10, padx=10)

        btn_ventas_directas = tk.Button(self.root, text="Ventas directas", command=self.ventas_directas)
        btn_ventas_directas.pack(pady=10, padx=20)

        self.root.bind('<Return>', lambda event: self.iniciar_habitacion())

    def actualizar_tiempos(self):
        for habitacion in self.habitaciones:
            tiempo_str = habitacion.get_tiempo_ocupacion()
            self.tabla.set(habitacion.numero, "Tiempo", tiempo_str)
        self.root.after(1000, self.actualizar_tiempos)

    def ventas_directas(self):
        # Crear una ventana para ventas directas
        self.ventas_directas_window = tk.Toplevel(self.root)
        self.ventas_directas_window.title("Ventas Directas")

        # Ingresar nombre de la persona
        tk.Label(self.ventas_directas_window, text="Nombre de la Persona:").pack(pady=5)
        self.nombre_persona_entry = tk.Entry(self.ventas_directas_window)
        self.nombre_persona_entry.pack(pady=5)

        # Seleccionar producto
        tk.Label(self.ventas_directas_window, text="Seleccione Producto:").pack(pady=5)
        self.producto_combobox = ttk.Combobox(self.ventas_directas_window, values=list(inventario.keys()), state="readonly")
        self.producto_combobox.pack(pady=5)

        # Ingresar cantidad
        tk.Label(self.ventas_directas_window, text="Cantidad:").pack(pady=5)
        self.cantidad_entry = tk.Entry(self.ventas_directas_window)
        self.cantidad_entry.pack(pady=5)

        # Botón para realizar la venta
        btn_vender = tk.Button(self.ventas_directas_window, text="Vender", command=self.realizar_venta_directa)
        btn_vender.pack(pady=10)

    def realizar_venta_directa(self):
        nombre_persona = self.nombre_persona_entry.get()
        producto_nombre = self.producto_combobox.get()
        cantidad = self.cantidad_entry.get()

        if not nombre_persona or not producto_nombre or not cantidad:
            messagebox.showerror("Error", "Todos los campos son obligatorios.")
            return

        if not cantidad.isdigit() or int(cantidad) <= 0:
            messagebox.showerror("Error", "La cantidad debe ser un número positivo.")
            return

        cantidad = int(cantidad)

        if producto_nombre in inventario:
            producto = inventario[producto_nombre]
            if producto.existencia >= cantidad:
                # Calcular el total
                total = producto.precio * cantidad

                # Reducir existencia en el inventario
                producto.existencia -= cantidad

                # Guardar la transacción en la base de datos
                zona_horaria = pytz.timezone('America/Bogota')
                fecha_actual = datetime.now(zona_horaria)
                fecha_formateada = fecha_actual.strftime('%Y-%m-%d %H:%M:%S')

                self.cursor.execute('''INSERT INTO transacciones (habitacion_numero, placa_vehiculo, tiempo_ocupacion, producto_nombre, total, fecha)
                                    VALUES (?, ?, ?, ?, ?, ?)''', 
                                    (None, None, None, producto_nombre, total, fecha_formateada))
                self.conn.commit()

                messagebox.showinfo("Venta Realizada", f"Se ha vendido {cantidad} de {producto_nombre} por un total de ${total:.2f}.")
                self.ventas_directas_window.destroy()
            else:
                messagebox.showerror("Error", f"No hay suficiente existencia de {producto_nombre}. Disponibles: {producto.existencia}")
        else:
            messagebox.showerror("Error", f"Producto {producto_nombre} no encontrado en el inventario.")
       

    def iniciar_habitacion(self):
        self.inicar_habitacion_window = tk.Toplevel(self.root)
        self.inicar_habitacion_window.title("Iniciar Habitación")

        tk.Label(self.inicar_habitacion_window, text="Placa del Vehículo").pack(pady=5)
        self.placa_entry = tk.Entry(self.inicar_habitacion_window)
        self.placa_entry.pack(pady=5)

        tk.Label(self.inicar_habitacion_window, text="Seleccione habitación:").pack(pady=5)
        self.habitacion_combobox = ttk.Combobox(self.inicar_habitacion_window, values=[habitacion.numero for habitacion in self.habitaciones], state="readonly")
        self.habitacion_combobox.pack(pady=5)

        btn_iniciar = tk.Button(self.inicar_habitacion_window, text="Iniciar", command=self.iniciar)
        btn_iniciar.pack(pady=10)

    def validar_placa(self, placa):
        return bool(re.match(r'^[A-Za-z0-9]{6}$', placa))
    
    def verificar_placa_duplicada(self, placa):
        for habitacion in self.habitaciones:
            if habitacion.placa_vehiculo == placa:
                return True
        return False


    def iniciar(self):
        item = self.habitacion_combobox.get()
        placa = self.placa_entry.get()
        
        if self.validar_placa(placa):
            if self.verificar_placa_duplicada(placa):
                messagebox.showwarning("Advertencia", "La placa del vehículo ya está en uso.")
                return
            
            if item:
                num_habitacion = int(item)
                habitacion = self.habitaciones[num_habitacion - 1]
                
                if not habitacion.ocupada:
                    habitacion.iniciar()
                    habitacion.placa_vehiculo = placa
                    self.inicar_habitacion_window.destroy()
                    
                    # Actualizar el Treeview con la nueva placa
                    self.tabla.item(habitacion.numero, values=(habitacion.numero, placa, "Ocupada", "0:00:00", "-", "-"))
                    self.tabla.set(item, "Placa", placa)
                    self.tabla.set(item, "Estado", "Ocupada")
                    self.tabla.set(item, "Tiempo", "0:00:00")
                    self.tabla.set(item, "Productos", "-")
                    self.tabla.set(item, "Cobrar", "-")
                else:
                    messagebox.showwarning("Advertencia", "La habitación ya está ocupada.")
        else:
            messagebox.showerror("Error", "La placa del vehículo debe tener exactamente 6 caracteres (letras y números).")


    def abrir_agregar_producto(self):
        agregar_producto_window = tk.Toplevel(self.root)
        agregar_producto_window.title("Agregar Producto")

        tk.Label(agregar_producto_window, text="Seleccione habitación:").pack(pady=5)
        habitacion_combobox = ttk.Combobox(agregar_producto_window, values=[habitacion.numero for habitacion in self.habitaciones if habitacion.ocupada], state="readonly")
        habitacion_combobox.pack(pady=5)

        tk.Label(agregar_producto_window, text="Seleccione producto:").pack(pady=5)
        producto_combobox = ttk.Combobox(agregar_producto_window, values=list(inventario.keys()), state="readonly")
        producto_combobox.pack(pady=5)

        tk.Label(agregar_producto_window, text="Cantidad:").pack(pady=5)
        cantidad_entry = tk.Entry(agregar_producto_window)
        cantidad_entry.pack(pady=5)

        def agregar_producto():
            num_habitacion = int(habitacion_combobox.get())
            producto_nombre = producto_combobox.get()
            cantidad = int(cantidad_entry.get())

            habitacion = self.habitaciones[num_habitacion - 1]
            producto = inventario[producto_nombre]

            habitacion.agregar_producto(producto, cantidad)
            self.tabla.set(num_habitacion, "Productos", ", ".join([f"{producto}: {cantidad}" for producto, cantidad in habitacion.productos.items()]))
            agregar_producto_window.destroy()

        btn_agregar = tk.Button(agregar_producto_window, text="Agregar", command=agregar_producto)
        btn_agregar.pack(pady=10)

    def abrir_cobrar(self):
        cobrar_window = tk.Toplevel(self.root)
        cobrar_window.title("Cobrar")


        tk.Label(cobrar_window, text="Seleccione habitación:").pack(pady=5)
        habitacion_combobox = ttk.Combobox(cobrar_window, values=[habitacion.numero for habitacion in self.habitaciones if habitacion.ocupada], state="readonly")
        habitacion_combobox.pack(pady=5)

    def abrir_cobrar(self):
        if "cobrar" not in self.usuario_actual.permisos:
            messagebox.showwarning("Error", "No tienes permiso para cobrar.")
            return

        item_seleccionado = self.tabla.focus()
        if item_seleccionado:
            numero = int(self.tabla.item(item_seleccionado, "values")[0])
            habitacion = self.habitaciones[numero - 1]
            if habitacion.ocupada:
                total = habitacion.calcular_total(tarifa_por_hora)

                self.cobrar_window = tk.Toplevel(self.root)
                self.cobrar_window.title(f"Cobrar - Habitación {numero}")
                self.cobrar_window.geometry("300x250")

                tk.Label(self.cobrar_window, text=f"Habitación: {numero}", font=("Helvetica", 14, "bold")).pack(pady=10)
                tk.Label(self.cobrar_window, text=f"Placa del Vehículo: {habitacion.placa_vehiculo}", font=("Helvetica", 14, "bold")).pack(pady=5)

                tk.Label(self.cobrar_window, text="Productos:").pack(anchor="w", padx=10)
                for producto, cantidad in habitacion.productos.items():
                    tk.Label(self.cobrar_window, text=f"- {producto}: {cantidad}").pack(anchor="w", padx=20)

                tiempo_str = habitacion.get_tiempo_ocupacion()
                tk.Label(self.cobrar_window, text=f"Tiempo: {tiempo_str}").pack(anchor="w", padx=10)

                tk.Label(self.cobrar_window, text=f"Total a Cobrar: ${total:.2f}", font=("Helvetica", 12, "bold")).pack(pady=10)

                btn_confirmar = tk.Button(self.cobrar_window, text="Confirmar Cobro", command=lambda: self.confirmar_cobro(numero))
                btn_confirmar.pack(pady=10, padx=10)
            else:
                messagebox.showwarning("Error", "La habitación no está ocupada.")
        else:
            messagebox.showwarning("Error", "Por favor, seleccione una habitación para cobrar.")


    def confirmar_cobro(self, numero):
        habitacion = self.habitaciones[numero - 1]
        elapsed_time = time.time() - habitacion.start_time
        total = habitacion.calcular_total(tarifa_por_hora)
        tiempo_ocupacion = habitacion.get_tiempo_ocupacion()
        productos = habitacion.productos.copy()

        # Define la zona horaria de Colombia
        zona_horaria = pytz.timezone('America/Bogota')
        fecha_actual = datetime.now(zona_horaria)
        fecha_formateada = fecha_actual.strftime('%Y-%m-%d %H:%M:%S')

        # Verifica que el tiempo transcurrido sea mayor a 5 minutos antes de realizar el cobro
        if elapsed_time < 300:
            total = 0

        # Asegurarse de que el total esté correctamente calculado
        if total == 0 and productos and elapsed_time >= 300:
            # Si hay productos pero el total es cero y ha pasado más de 5 minutos, recalcular el total
            total_productos = sum(inventario[producto].precio * cantidad for producto, cantidad in productos.items())
            total = total_productos  # Actualizar el total con los productos

        if productos and elapsed_time >= 300:  # Si el diccionario no está vacío y han pasado más de 5 minutos
            for producto, cantidad in productos.items():
                self.cursor.execute('''INSERT INTO transacciones (habitacion_numero, placa_vehiculo, tiempo_ocupacion, producto_nombre, total, fecha)
                                    VALUES (?, ?, ?, ?, ?, ?)''', 
                                    (numero, habitacion.placa_vehiculo, tiempo_ocupacion, producto, total, fecha_formateada))
        elif elapsed_time >= 300:  # Si el diccionario está vacío pero han pasado más de 5 minutos
            self.cursor.execute('''INSERT INTO transacciones (habitacion_numero, placa_vehiculo, tiempo_ocupacion, producto_nombre, total, fecha)
                                VALUES (?, ?, ?, ?, ?, ?)''', 
                                (numero, habitacion.placa_vehiculo, tiempo_ocupacion, None, total, fecha_formateada))

        self.conn.commit()


        messagebox.showinfo("Cobro Realizado", f"Se ha cobrado ${total:.2f} por la habitación {numero}")
        self.cobrar_window.destroy()
        habitacion.reiniciar()
        self.tabla.set(numero, "Placa", " ")  
        self.tabla.set(numero, "Estado", "Libre")
        self.tabla.set(numero, "Tiempo", "0:00:00")
        self.tabla.set(numero, "Productos", "-")
        self.tabla.item(numero, tags="")


    def abrir_historial(self):
        historial_window = tk.Toplevel(self.root)
        historial_window.title("Historial")

        tk.Label(historial_window, text="Seleccione habitación:").pack(pady=5)
        habitacion_combobox = ttk.Combobox(historial_window, values=[habitacion.numero for habitacion in self.habitaciones], state="readonly")
        habitacion_combobox.pack(pady=5)

        def ver_historial():
            num_habitacion = int(habitacion_combobox.get())
            habitacion = self.habitaciones[num_habitacion - 1]

            historial_text = tk.Text(historial_window, width=50, height=20)
            historial_text.pack(pady=5)

            for ocupacion in habitacion.historial:
                tiempo_ocupacion = ocupacion["tiempo"]
                productos = ocupacion["productos"]
                total = ocupacion["total"]
                historial_text.insert(tk.END, f"Placa del Vehículo: {habitacion.placa_vehiculo}\n")
                historial_text.insert(tk.END, f"Tiempo de ocupación: {tiempo_ocupacion / 3600:.2f} horas\n")
                historial_text.insert(tk.END, f"Productos consumidos: {productos}\n")
                historial_text.insert(tk.END, f"Total: ${total:.2f}\n")
                historial_text.insert(tk.END, "-" * 50 + "\n")

        btn_ver_historial = tk.Button(historial_window, text="Ver Historial", command=ver_historial)
        btn_ver_historial.pack(pady=10)


    def abrir_mover_habitacion(self):
        self.mover_habitacion_window = tk.Toplevel(self.root)
        self.mover_habitacion_window.title("Mover Tiempo y Productos")

        tk.Label(self.mover_habitacion_window, text="Habitación Origen:").pack(pady=5)
        self.habitacion_origen_combobox = ttk.Combobox(self.mover_habitacion_window, values=[habitacion.numero for habitacion in self.habitaciones], state="readonly")
        self.habitacion_origen_combobox.pack(pady=5)

        tk.Label(self.mover_habitacion_window, text="Habitación Destino:").pack(pady=5)
        self.habitacion_destino_combobox = ttk.Combobox(self.mover_habitacion_window, values=[habitacion.numero for habitacion in self.habitaciones], state="readonly")
        self.habitacion_destino_combobox.pack(pady=5)

        btn_mover = tk.Button(self.mover_habitacion_window, text="Mover", command=self.realizar_mover_habitacion)
        btn_mover.pack(pady=10)

    def realizar_mover_habitacion(self):
        origen = int(self.habitacion_origen_combobox.get())
        destino = int(self.habitacion_destino_combobox.get())
        self.mover_habitacion(origen, destino)
        self.mover_habitacion_window.destroy()

    def mover_habitacion(self, origen, destino):
        habitacion_origen = self.habitaciones[origen - 1]
        habitacion_destino = self.habitaciones[destino - 1]

        if habitacion_origen.ocupada and not habitacion_destino.ocupada:
            # Mover tiempo de ocupación
            habitacion_destino.start_time = habitacion_origen.start_time

            # Mover productos
            habitacion_destino.productos = habitacion_origen.productos.copy()

            # Mover placa de vehículo
            habitacion_destino.placa_vehiculo = habitacion_origen.placa_vehiculo

            # Actualizar estados
            habitacion_destino.ocupada = True
            habitacion_origen.ocupada = False

            # Limpiar habitación origen
            habitacion_origen.start_time = None
            habitacion_origen.productos = {}
            habitacion_origen.placa_vehiculo = None

            # Actualizar interfaz gráfica
            self.tabla.set(origen, "Estado", "Libre")
            self.tabla.set(origen, "Tiempo", "00:00:00")
            self.tabla.set(origen, "Productos", " ")
            self.tabla.set(origen, "Placa", "-")

            self.tabla.set(destino, "Estado", "Ocupada")
            self.tabla.set(destino, "Tiempo", habitacion_destino.get_tiempo_ocupacion())
            productos_str = ", ".join([f"{producto}: {cantidad}" for producto, cantidad in habitacion_destino.productos.items()])
            self.tabla.set(destino, "Productos", productos_str)
            self.tabla.set(destino, "Placa", habitacion_destino.placa_vehiculo)

        else:
            messagebox.showwarning("Error", "La habitación de destino está ocupada o la habitación de origen no está ocupada.")



    def mostrar_interfaz_gestion_inventario(self):
        # Interfaz principal de gestión de inventario
        gestionar_inventario_window = tk.Toplevel(self.root)
        gestionar_inventario_window.title("Gestionar Inventario")
        gestionar_inventario_window.geometry("600x500")

        tk.Label(gestionar_inventario_window, text="Productos Actuales en Inventario", font=("Helvetica", 14, "bold")).pack(pady=5)
        
        columnas = ("nombre", "precio", "existencia")
        self.tabla_inventario = ttk.Treeview(gestionar_inventario_window, columns=columnas, show="headings")
        self.tabla_inventario.heading("nombre", text="Nombre")
        self.tabla_inventario.heading("precio", text="Precio")
        self.tabla_inventario.heading("existencia", text="Existencia")
        self.tabla_inventario.pack(pady=10, fill="x")

        self.actualizar_tabla_inventario()
        
        tk.Label(gestionar_inventario_window, text="Agregar Nuevo Producto", font=("Helvetica", 14, "bold")).pack(pady=5)
        frame_nuevo_producto = tk.Frame(gestionar_inventario_window)
        frame_nuevo_producto.pack(pady=5)
        tk.Label(frame_nuevo_producto, text="Nombre:").pack(side="left")
        entry_nombre_producto = tk.Entry(frame_nuevo_producto)
        entry_nombre_producto.pack(side="left", padx=5)
        tk.Label(frame_nuevo_producto, text="Precio:").pack(side="left")
        entry_precio_producto = tk.Entry(frame_nuevo_producto)
        entry_precio_producto.pack(side="left", padx=5)
        tk.Label(frame_nuevo_producto, text="Existencia:").pack(side="left")
        entry_existencia_producto = tk.Entry(frame_nuevo_producto)
        entry_existencia_producto.pack(side="left", padx=5)
        btn_agregar_producto = tk.Button(gestionar_inventario_window, text="Agregar Producto", command=lambda: self.validar_y_agregar_producto(entry_nombre_producto, entry_precio_producto, entry_existencia_producto))
        btn_agregar_producto.pack(pady=5)

        tk.Label(gestionar_inventario_window, text="Eliminar Producto", font=("Helvetica", 14, "bold")).pack(pady=5)
        frame_eliminar_producto = tk.Frame(gestionar_inventario_window)
        frame_eliminar_producto.pack(pady=5)
        productos_combobox = ttk.Combobox(frame_eliminar_producto, values=list(inventario.keys()), state="readonly")
        productos_combobox.pack(side="left", padx=5)
        btn_eliminar_producto = tk.Button(frame_eliminar_producto, text="Eliminar Producto", command=lambda: self.eliminar_producto(productos_combobox.get()))
        btn_eliminar_producto.pack(side="left")
        
        tk.Label(gestionar_inventario_window, text="Modificar Precio", font=("Helvetica", 14, "bold")).pack(pady=5)
        frame_modificar_precio = tk.Frame(gestionar_inventario_window)
        frame_modificar_precio.pack(pady=5)
        productos_combobox_mod = ttk.Combobox(frame_modificar_precio, values=list(inventario.keys()), state="readonly")
        productos_combobox_mod.pack(side="left", padx=5)
        tk.Label(frame_modificar_precio, text="Nuevo Precio:").pack(side="left")
        entry_nuevo_precio = tk.Entry(frame_modificar_precio)
        entry_nuevo_precio.pack(side="left", padx=5)
        btn_modificar_precio = tk.Button(frame_modificar_precio, text="Modificar Precio", command=lambda: self.modificar_precio(productos_combobox_mod.get(), float(entry_nuevo_precio.get())))
        btn_modificar_precio.pack(side="left")

    def actualizar_tabla_inventario(self):
        # Limpiar tabla existente
        for item in self.tabla_inventario.get_children():
            self.tabla_inventario.delete(item)
        # Llenar tabla con datos actuales del inventario
        for producto in inventario.values():
            self.tabla_inventario.insert("", "end", values=(producto.nombre, producto.precio, producto.existencia))

    def validar_y_agregar_producto(self, entry_nombre_producto, entry_precio_producto, entry_existencia_producto):
        nombre = entry_nombre_producto.get().strip()
        precio = entry_precio_producto.get().strip()
        existencia = entry_existencia_producto.get().strip()

        if not nombre or not precio or not existencia:
            messagebox.showerror("Error", "Todos los campos son obligatorios.")
            return

        try:
            precio = float(precio)
        except ValueError:
            messagebox.showerror("Error", "El precio debe ser un número válido.")
            return

        try:
            existencia = int(existencia)
        except ValueError:
            messagebox.showerror("Error", "La existencia debe ser un número entero válido.")
            return

        if nombre in inventario:
            messagebox.showerror("Error", "El producto ya existe en el inventario.")
            return

        nuevo_producto = Producto(nombre, precio, existencia)
        inventario[nombre] = nuevo_producto
        self.tabla_inventario.insert("", "end", values=(nombre, precio, existencia))
        messagebox.showinfo("Éxito", "Producto agregado correctamente.")
        entry_nombre_producto.delete(0, tk.END)
        entry_precio_producto.delete(0, tk.END)
        entry_existencia_producto.delete(0, tk.END)

        # Guardar el inventario actualizado como CSV
        self.guardar_inventario_csv()

    def eliminar_producto(self, nombre_producto):
        if nombre_producto in inventario:
            del inventario[nombre_producto]
            self.actualizar_tabla_inventario()
            messagebox.showinfo("Éxito", "Producto eliminado correctamente.")
            # Guardar el inventario actualizado como CSV
            self.guardar_inventario_csv()
        else:
            messagebox.showerror("Error", "El producto no existe en el inventario.")

    def modificar_precio(self, nombre_producto, nuevo_precio):
        if nombre_producto in inventario:
            inventario[nombre_producto].precio = nuevo_precio
            self.actualizar_tabla_inventario()
            messagebox.showinfo("Éxito", "Precio modificado correctamente.")
            # Guardar el inventario actualizado como CSV
            self.guardar_inventario_csv()
        else:
            messagebox.showerror("Error", "El producto no existe en el inventario.")

    def abrir_gestionar_usuarios(self):
        if "gestionar_usuarios" not in self.usuario_actual.permisos:
            messagebox.showwarning("Error", "No tienes permiso para gestionar usuarios.")
            return

        gestionar_usuarios_window = tk.Toplevel(self.root)
        gestionar_usuarios_window.title("Gestionar Usuarios")

        lista_usuarios = tk.Listbox(gestionar_usuarios_window)
        lista_usuarios.pack(fill="both", expand=True, padx=10, pady=10)

        for usuario in self.usuarios:
            lista_usuarios.insert("end", usuario.nombre)

        def actualizar_lista():
            lista_usuarios.delete(0, "end")
            for usuario in self.usuarios:
                lista_usuarios.insert("end", usuario.nombre)

        def agregar_usuario():
            nombre = entry_nombre_usuario.get()
            contrasena = entry_contrasena_usuario.get()
            permisos = entry_permisos.get().split(",")
            self.usuarios.append(Usuario(nombre, contrasena, permisos))
            messagebox.showinfo("Usuario Agregado", f"Se ha agregado el usuario {nombre}.")
            actualizar_lista()

        def eliminar_usuario():
            seleccion = lista_usuarios.curselection()
            if seleccion:
                nombre_usuario = lista_usuarios.get(seleccion)
                for usuario in self.usuarios:
                    if usuario.nombre == nombre_usuario:
                        self.usuarios.remove(usuario)
                        messagebox.showinfo("Usuario Eliminado", f"Se ha eliminado el usuario {nombre_usuario}.")
                        actualizar_lista()

        def cambiar_contrasena():
            seleccion = lista_usuarios.curselection()
            if seleccion:
                usuario_nombre = lista_usuarios.get(seleccion)
                nueva_contrasena = entry_nueva_contrasena.get()
                for usuario in self.usuarios:
                    if usuario.nombre == usuario_nombre:
                        usuario.contrasena = nueva_contrasena
                        messagebox.showinfo("Cambio de Contraseña", f"Contraseña de {usuario_nombre} ha sido cambiada.")

        frame_formulario = tk.Frame(gestionar_usuarios_window)
        frame_formulario.pack(fill="x")

        tk.Label(frame_formulario, text="Nombre:").pack(side="left")
        entry_nombre_usuario = tk.Entry(frame_formulario)
        entry_nombre_usuario.pack(side="left", padx=5)

        tk.Label(frame_formulario, text="Contraseña:").pack(side="left")
        entry_contrasena_usuario = tk.Entry(frame_formulario)
        entry_contrasena_usuario.pack(side="left", padx=5)

        tk.Label(frame_formulario, text="Permisos (separados por comas):").pack(side="left")
        permisos_var = tk.StringVar()
        entry_permisos = tk.Entry(frame_formulario, textvariable=permisos_var)
        entry_permisos.pack(side="left", padx=5)

        btn_agregar = tk.Button(frame_formulario, text="Agregar", command=agregar_usuario)
        btn_agregar.pack(side="left", padx=5)

        btn_eliminar = tk.Button(gestionar_usuarios_window, text="Eliminar", command=eliminar_usuario)
        btn_eliminar.pack(pady=10)

        frame_cambiar_contrasena = tk.Frame(gestionar_usuarios_window)
        frame_cambiar_contrasena.pack(fill="x", pady=10)

        tk.Label(frame_cambiar_contrasena, text="Nueva Contraseña:").pack(side="left")
        entry_nueva_contrasena = tk.Entry(frame_cambiar_contrasena)
        entry_nueva_contrasena.pack(side="left", padx=5)

        btn_cambiar_contrasena = tk.Button(frame_cambiar_contrasena, text="Cambiar Contraseña", command=cambiar_contrasena)
        btn_cambiar_contrasena.pack(side="left", padx=5)

if __name__ == "__main__":
    root = tk.Tk()
    app = MotelApp(root)
    root.mainloop()
