import tkinter as tk
from tkinter import scrolledtext, messagebox, font as tkfont, PanedWindow
import math  # For pi


try:
    import matplotlib

    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
    import networkx as nx

    VISUALIZATION_ENABLED = True
except ImportError:
    VISUALIZATION_ENABLED = False
    print("Предупреждение: Библиотеки Matplotlib или NetworkX не найдены. Визуализация графа будет отключена.")
    print("Для включения визуализации, пожалуйста, установите их: pip install matplotlib networkx")


    class FigureCanvasTkAgg:
        def __init__(self, figure, master): self.master = master

        def get_tk_widget(self): return tk.Frame(self.master)

        def draw_idle(self): pass

        def mpl_connect(self, event_name, callback): pass


    class NavigationToolbar2Tk:
        def __init__(self, canvas, master): pass

        def update(self): pass


    class Figure:  # type: ignore
        def __init__(self, figsize, dpi, facecolor): pass

        def add_subplot(self, *args, **kwargs): return AxesMock()

        def tight_layout(self, pad=None): pass


    class AxesMock:
        def cla(self): pass

        def set_facecolor(self, color): pass

        def axis(self, state): pass

        def text(self, *args, **kwargs): pass

        def get_xlim(self): return (0, 1)

        def get_ylim(self): return (0, 1)

        def set_xlim(self, xmin, xmax): pass

        def set_ylim(self, ymin, ymax): pass

        def has_data(self): return False  # Add for compatibility

        def autoscale_view(self): pass  # Add for compatibility



def find_cycle_util(node, graph, visited, recursion_stack, path_accumulator):
    visited.add(node)
    recursion_stack.add(node)
    path_accumulator.append(node)
    for neighbor in graph.get(node, []):
        if neighbor not in visited:
            cycle = find_cycle_util(neighbor, graph, visited, recursion_stack, path_accumulator)
            if cycle:
                return cycle
        elif neighbor in recursion_stack:
            try:
                start_index = path_accumulator.index(neighbor)
                return path_accumulator[start_index:]
            except ValueError:
                return []
    recursion_stack.remove(node)
    path_accumulator.pop()
    return None


def detect_deadlock_wfg(graph):
    if not graph:
        return None
    all_nodes = set(graph.keys())
    for dependencies in graph.values():
        all_nodes.update(dependencies)
    visited = set()
    recursion_stack = set()
    for node in sorted(list(all_nodes)):
        if node not in visited:
            path_accumulator = []
            cycle = find_cycle_util(node, graph, visited, recursion_stack, path_accumulator)
            if cycle:
                return cycle
    return None



class DeadlockApp:
    def __init__(self, master):
        self.master = master
        master.title("Детектор Тупиков (Wait-For Graph) с Визуализацией")
        master.geometry("950x750")  # Ширина x Высота
        master.minsize(800, 600)  # Минимальный размер окна

        # Стили
        self.default_font = tkfont.nametofont("TkDefaultFont")
        self.default_font.configure(size=11)
        self.header_font = tkfont.Font(family="Arial", size=16, weight="bold")
        self.label_font = tkfont.Font(family="Arial", size=12, weight="normal")
        self.text_font = tkfont.Font(family="Consolas", size=11)

        # Цвета
        self.bg_color = "#e9ebee"  # Светло-серый фон
        self.frame_bg_color = "#ffffff"  # Белый фон для фреймов
        self.button_color = "#4CAF50"  # Зеленая кнопка
        self.button_fg_color = "#ffffff"  # Белый текст на кнопке
        self.clear_button_color = "#f44336"  # Красная кнопка
        self.text_bg_color = "#fdfdfe"
        self.error_color_fg = "#D32F2F"  # Темно-красный для текста ошибки
        self.success_color_fg = "#388E3C"  # Темно-зеленый для текста успеха
        self.info_color_fg = "#1976D2"  # Темно-синий для инфо текста

        self.node_color_default = "skyblue"
        self.node_color_cycle = "#ff796c"  # Ярко-красный для узлов цикла
        self.edge_color_default = "grey"
        self.edge_color_cycle = self.error_color_fg  # Темно-красный для ребер цикла

        master.configure(bg=self.bg_color)

        # --- Переменные для перетаскивания вершин ---
        self.graph_G = None  # NetworkX DiGraph object
        self.graph_pos = None  # Словарь позиций вершин {node: (x,y)}
        self.dragged_node_id = None  # ID перетаскиваемой вершины
        self.drag_offset_x = 0  # Смещение курсора относительно центра вершины по X
        self.drag_offset_y = 0  # Смещение курсора относительно центра вершины по Y
        self.parsed_graph_for_draw = None  # Сохраняем структуру графа для перерисовки
        self.cycle_nodes_for_draw = None  # Сохраняем цикл для перерисовки
        self.node_size_val = 1200  # Стандартный размер вершины (площадь в points^2)

        # --- Основной разделяемый контейнер ---
        self.paned_window = PanedWindow(master, orient=tk.VERTICAL, sashrelief=tk.RAISED, bg=self.bg_color, sashwidth=6)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Верхняя панель для управления ---
        control_panel_outer_frame = tk.Frame(self.paned_window, bg=self.bg_color)  # Внешний фрейм для отступов
        control_panel_frame = tk.Frame(control_panel_outer_frame, bg=self.frame_bg_color, bd=1, relief=tk.SOLID)

        # Заголовок приложения
        tk.Label(control_panel_frame, text="Детектор Тупиков в Системе", font=self.header_font,
                 bg=self.frame_bg_color, fg="#333333", pady=15).pack(fill=tk.X)

        # Секция ввода данных
        input_section_frame = tk.Frame(control_panel_frame, bg=self.frame_bg_color, padx=15, pady=10)
        input_section_frame.pack(fill=tk.BOTH, expand=True)  # Разрешаем расширение

        tk.Label(input_section_frame, text="Определения графа ожидания (WFG):",
                 font=self.label_font, bg=self.frame_bg_color, anchor='w').pack(fill=tk.X)

        instruction_text = (
            "Формат: 'P_ожидающий -> P_удерживающий' или 'P_ожидающий P_удерживающий'.\n"
            "Каждая зависимость на новой строке. Комментарии с '#'."
        )
        tk.Label(input_section_frame, text=instruction_text, justify=tk.LEFT,
                 bg=self.frame_bg_color, fg="#555555", anchor='w', wraplength=master.winfo_width() - 60).pack(fill=tk.X,
                                                                                                              pady=(
                                                                                                                  0, 5))

        self.input_area = scrolledtext.ScrolledText(input_section_frame, height=6,  # Уменьшил немного высоту
                                                    font=self.text_font,
                                                    bg=self.text_bg_color, relief=tk.SOLID, borderwidth=1,
                                                    padx=5, pady=5)
        self.input_area.pack(fill=tk.X, expand=True, pady=(0, 10))  # expand=True для поля ввода
        self.input_area.insert(tk.END,
    "# Пример с тупиком:\nP1 -> P2\nP2 -> P3\nP3 -> P1\nP4 -> P1\n\n# Пример без тупика:\nA -> B\nB -> C\nX -> Y")
        self.input_area.focus_set()

        # Кнопки управления
        button_frame = tk.Frame(input_section_frame, bg=self.frame_bg_color)
        button_frame.pack(pady=5)

        self.detect_button = tk.Button(button_frame, text="Обнаружить и Показать Граф",
                                       command=self.run_detection_and_draw,
                                       font=self.default_font, bg=self.button_color, fg=self.button_fg_color,
                                       relief=tk.RAISED, borderwidth=2, padx=12, pady=6, activebackground="#45a049")
        self.detect_button.pack(side=tk.LEFT, padx=10)

        self.clear_button = tk.Button(button_frame, text="Очистить Поля", command=self.clear_all,
                                      font=self.default_font, bg=self.clear_button_color, fg=self.button_fg_color,
                                      relief=tk.RAISED, borderwidth=2, padx=12, pady=6, activebackground="#e53935")
        self.clear_button.pack(side=tk.LEFT, padx=10)

        # Область вывода результата
        tk.Label(input_section_frame, text="Результат Анализа:",
                 font=self.label_font, bg=self.frame_bg_color, anchor='w').pack(fill=tk.X, pady=(10, 0))
        self.result_area = scrolledtext.ScrolledText(input_section_frame, height=3,  # Уменьшил высоту
                                                     font=self.text_font,
                                                     bg=self.text_bg_color, relief=tk.SOLID, borderwidth=1,
                                                     state=tk.DISABLED, padx=5, pady=5)
        self.result_area.pack(fill=tk.X, expand=True, pady=(0, 10))  # expand=True для поля результата

        control_panel_frame.pack(fill=tk.BOTH, expand=True, padx=5,
                                 pady=5)  # Упаковываем основной фрейм панели управления
        self.paned_window.add(control_panel_outer_frame, minsize=320)  # Минимальная высота для панели управления

        # --- Нижняя панель для визуализации графа ---
        graph_display_outer_frame = tk.Frame(self.paned_window, bg=self.bg_color)  # Внешний фрейм
        graph_display_frame = tk.Frame(graph_display_outer_frame, bg=self.frame_bg_color, bd=1, relief=tk.SOLID)

        if VISUALIZATION_ENABLED:
            tk.Label(graph_display_frame, text="Визуализация Графа Ожидания (WFG):",
                     font=self.label_font, bg=self.frame_bg_color, fg="#333333", pady=10).pack(fill=tk.X, padx=15)

            self.fig = Figure(figsize=(7, 5), dpi=100, facecolor=self.frame_bg_color)  # figsize влияет на пропорции
            self.ax = self.fig.add_subplot(111)
            self.ax.set_facecolor(self.frame_bg_color)  # Фон самого графика
            self.ax.axis('off')

            self.canvas = FigureCanvasTkAgg(self.fig, master=graph_display_frame)
            self.canvas_widget = self.canvas.get_tk_widget()
            self.canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=15, pady=(0, 5))

            # Добавление панели инструментов Matplotlib
            toolbar_frame = tk.Frame(graph_display_frame, bg=self.frame_bg_color)
            toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=15, pady=(0, 10))
            self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
            self.toolbar.update()  # type: ignore

            # Инициализация переменных для панорамирования и масштабирования
            self._pan_active = False
            self._pan_start_x = None
            self._pan_start_y = None
            self._pan_start_xlim = None
            self._pan_start_ylim = None

            # Подключение обработчиков событий мыши
            self.canvas.mpl_connect('scroll_event', self._on_scroll)
            self.canvas.mpl_connect('button_press_event', self._on_button_press)
            self.canvas.mpl_connect('motion_notify_event', self._on_motion)
            self.canvas.mpl_connect('button_release_event', self._on_button_release)

            self.draw_graph_visual(None, None, recalculate_layout_and_graph=True)  # Изначально рисуем пустой холст
        else:
            tk.Label(graph_display_frame, text="Визуализация графа отключена (отсутствуют Matplotlib/NetworkX).",
                     font=self.default_font, bg=self.frame_bg_color, fg="red").pack(pady=20, padx=15, fill=tk.BOTH,
                                                                                    expand=True)

        graph_display_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.paned_window.add(graph_display_outer_frame, minsize=300)  # Минимальная высота для панели графа

    # --- Обработчики событий мыши для графа ---
    def _on_scroll(self, event):
        if event.inaxes != self.ax or not VISUALIZATION_ENABLED:
            return

        if self.toolbar.mode == 'zoom rect':  # type: ignore
            return

        cur_xlim = self.ax.get_xlim()
        cur_ylim = self.ax.get_ylim()

        xdata = event.xdata
        ydata = event.ydata

        if xdata is None or ydata is None:
            xdata = (cur_xlim[0] + cur_xlim[1]) / 2.0
            ydata = (cur_ylim[0] + cur_ylim[1]) / 2.0

        scale_factor = 1.1
        if event.button == 'up':
            base_scale = 1 / scale_factor
        elif event.button == 'down':
            base_scale = scale_factor
        else:
            return

        new_width = (cur_xlim[1] - cur_xlim[0]) * base_scale
        new_height = (cur_ylim[1] - cur_ylim[0]) * base_scale

        relx = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
        rely = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])

        self.ax.set_xlim([xdata - new_width * (1 - relx), xdata + new_width * (relx)])
        self.ax.set_ylim([ydata - new_height * (1 - rely), ydata + new_height * (rely)])
        self.canvas.draw_idle()

    def _on_button_press(self, event):
        if event.inaxes != self.ax or not VISUALIZATION_ENABLED:
            return

        # Панорамирование левой кнопкой мыши
        if event.button == 1:
            if self.toolbar.mode in ['pan/zoom', 'zoom rect']:  # type: ignore
                return
            self._pan_active = True
            self._pan_start_x = event.xdata
            self._pan_start_y = event.ydata
            self._pan_start_xlim = self.ax.get_xlim()
            self._pan_start_ylim = self.ax.get_ylim()
            self.canvas_widget.config(cursor="fleur")

        # Перетаскивание вершины правой кнопкой мыши
        elif event.button == 3:
            if event.xdata is None or event.ydata is None: return
            if not self.graph_pos or not self.graph_G or not self.graph_G.nodes(): return

            click_x, click_y = event.xdata, event.ydata

            # Рассчитываем порог для клика на вершине в координатах данных
            # Это приблизительный расчет, так как размер вершины задан в points^2
            node_radius_points = math.sqrt(self.node_size_val / math.pi)
            node_diameter_points = 2 * node_radius_points

            ax_bbox = self.ax.get_window_extent()
            if ax_bbox.width == 0 or ax_bbox.height == 0: return

            data_xlim = self.ax.get_xlim()
            data_ylim = self.ax.get_ylim()
            data_width = data_xlim[1] - data_xlim[0]
            data_height = data_ylim[1] - data_ylim[0]
            if data_width == 0 or data_height == 0: return

            # Преобразование диаметра из точек в пиксели, затем в единицы данных
            # dpi/72.0 - коэффициент для преобразования points в pixels (1 point = 1/72 inch)
            node_diameter_pixels = node_diameter_points * (self.fig.dpi / 72.0)

            # Средний размер пикселя в единицах данных
            # (Это упрощение, если aspect ratio осей не сохранен, может быть неточно)
            pixel_width_in_data_units = data_width / ax_bbox.width
            pixel_height_in_data_units = data_height / ax_bbox.height

            # Используем большее из двух, чтобы быть более снисходительным к клику
            node_radius_data_units_approx = (node_diameter_pixels / 2.0) * max(pixel_width_in_data_units,
                                                                               pixel_height_in_data_units)

            min_dist_sq = float('inf')
            target_node = None

            for node_id, (px, py) in self.graph_pos.items():
                dist_sq = (px - click_x) ** 2 + (py - click_y) ** 2
                if dist_sq < min_dist_sq:
                    min_dist_sq = dist_sq
                    target_node = node_id

            if target_node is not None and math.sqrt(min_dist_sq) < node_radius_data_units_approx:
                self.dragged_node_id = target_node
                self.drag_offset_x = self.graph_pos[self.dragged_node_id][0] - click_x
                self.drag_offset_y = self.graph_pos[self.dragged_node_id][1] - click_y
                self.canvas_widget.config(cursor="hand2")  # или "grabbing"

    def _on_motion(self, event):
        if not VISUALIZATION_ENABLED: return

        # Обработка панорамирования (левая кнопка)
        if self._pan_active and event.inaxes == self.ax:
            if self._pan_start_x is None or self._pan_start_y is None or \
                    event.xdata is None or event.ydata is None:
                return
            dx = event.xdata - self._pan_start_x
            dy = event.ydata - self._pan_start_y
            if self._pan_start_xlim is not None and self._pan_start_ylim is not None:
                self.ax.set_xlim(self._pan_start_xlim[0] - dx, self._pan_start_xlim[1] - dx)
                self.ax.set_ylim(self._pan_start_ylim[0] - dy, self._pan_start_ylim[1] - dy)
                self.canvas.draw_idle()

        # Обработка перетаскивания вершины (правая кнопка)
        elif self.dragged_node_id is not None and event.inaxes == self.ax:
            if event.xdata is None or event.ydata is None: return

            mouse_x, mouse_y = event.xdata, event.ydata
            new_node_x = mouse_x + self.drag_offset_x
            new_node_y = mouse_y + self.drag_offset_y

            self.graph_pos[self.dragged_node_id] = (new_node_x, new_node_y)
            # Перерисовываем граф с обновленными позициями, не пересчитывая layout
            self.draw_graph_visual(self.parsed_graph_for_draw, self.cycle_nodes_for_draw,
                                   recalculate_layout_and_graph=False)

    def _on_button_release(self, event):
        if not VISUALIZATION_ENABLED: return

        # Завершение панорамирования (левая кнопка)
        if event.button == 1 and self._pan_active:
            self._pan_active = False
            self._pan_start_x = None
            self._pan_start_y = None
            self._pan_start_xlim = None
            self._pan_start_ylim = None
            self.canvas_widget.config(cursor="")

        # Завершение перетаскивания вершины (правая кнопка)
        elif event.button == 3 and self.dragged_node_id is not None:
            self.dragged_node_id = None
            self.canvas_widget.config(cursor="")
            # Граф уже перерисован в _on_motion

    def parse_input(self, input_text):
        # (без изменений)
        graph = {}
        lines = input_text.strip().split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '->' in line:
                parts = line.split('->', 1)
            else:
                parts = line.split(None, 1)
            if len(parts) != 2:
                messagebox.showerror("Ошибка Ввода",
                                     f"Неверный формат в строке {i + 1}: '{line}'.\n"
                                     "Используйте 'P1 -> P2' или 'P1 P2'.")
                return None
            p_waiting = parts[0].strip()
            p_holding = parts[1].strip()
            if not p_waiting or not p_holding:
                messagebox.showerror("Ошибка Ввода",
                                     f"Пустое имя процесса в строке {i + 1}: '{line}'.")
                return None
            if ' ' in p_waiting or ' ' in p_holding:
                messagebox.showerror("Ошибка Ввода",
                                     f"Имена процессов не должны содержать пробелов. Строка {i + 1}: '{line}'.")
                return None
            if p_waiting not in graph:
                graph[p_waiting] = []
            if p_holding not in graph.get(p_waiting, []):
                graph[p_waiting].append(p_holding)
        return graph

    def display_result(self, text, color_fg):
        self.result_area.config(state=tk.NORMAL)
        self.result_area.delete("1.0", tk.END)
        self.result_area.insert(tk.END, text)
        self.result_area.tag_add("result_style", "1.0", tk.END)
        self.result_area.tag_config("result_style", foreground=color_fg, font=self.text_font)
        self.result_area.config(state=tk.DISABLED)

    def draw_graph_visual(self, current_parsed_graph, cycle_nodes_list=None, recalculate_layout_and_graph=False):
        if not VISUALIZATION_ENABLED:
            return

        current_xlim = None
        current_ylim = None
        if not recalculate_layout_and_graph and hasattr(self.ax,
                                                        'has_data') and self.ax.has_data():  # Сохраняем зум при перетаскивании
            current_xlim = self.ax.get_xlim()
            current_ylim = self.ax.get_ylim()
            # Избегаем сброса на дефолтные (0,1) если это не действительный зум
            if current_xlim == (0.0, 1.0) and current_ylim == (0.0, 1.0):
                if hasattr(self, '_last_valid_xlim_for_redraw'):
                    current_xlim = self._last_valid_xlim_for_redraw
                    current_ylim = self._last_valid_ylim_for_redraw
                else:  # Если это первый рендер или после clear, где (0,1) это нормально
                    current_xlim = None
                    current_ylim = None

        self.ax.cla()
        self.ax.set_facecolor(self.frame_bg_color)
        self.ax.axis('off')

        if current_parsed_graph is None:
            self.ax.text(0.5, 0.5, "Граф для отображения отсутствует.",
                         horizontalalignment='center', verticalalignment='center',
                         transform=self.ax.transAxes, fontdict={'size': 12, 'color': 'grey'})
            self.graph_G = None
            self.graph_pos = None
            if hasattr(self, '_last_valid_xlim_for_redraw'):
                del self._last_valid_xlim_for_redraw
                del self._last_valid_ylim_for_redraw
            self.canvas.draw_idle()
            return

        if recalculate_layout_and_graph or self.graph_G is None or self.graph_pos is None:
            new_G = nx.DiGraph()
            all_nodes_in_parsed_graph = set(current_parsed_graph.keys())
            for dependencies in current_parsed_graph.values():
                all_nodes_in_parsed_graph.update(dependencies)

            if not all_nodes_in_parsed_graph and not current_parsed_graph:  # Явно пустой граф из ввода
                self.ax.text(0.5, 0.5, "Граф пуст (нет узлов).",
                             horizontalalignment='center', verticalalignment='center',
                             transform=self.ax.transAxes, fontdict={'size': 12, 'color': 'grey'})
                self.graph_G = new_G  # Пустой граф
                self.graph_pos = {}  # Пустые позиции
                self.canvas.draw_idle()
                return

            for node_name in all_nodes_in_parsed_graph:
                new_G.add_node(node_name)
            for u, dependencies in current_parsed_graph.items():
                for v in dependencies:
                    new_G.add_edge(u, v)
            self.graph_G = new_G

            if not self.graph_G.nodes():
                self.graph_pos = {}
            else:
                try:
                    self.graph_pos = nx.kamada_kawai_layout(self.graph_G)
                except Exception:
                    try:
                        self.graph_pos = nx.spring_layout(self.graph_G, k=0.7, iterations=70, seed=42)
                    except Exception:
                        self.graph_pos = nx.circular_layout(self.graph_G)

        # Проверка после попытки создания/использования self.graph_G и self.graph_pos
        if not self.graph_G or not self.graph_G.nodes():
            self.ax.text(0.5, 0.5, "Граф не содержит узлов для отображения.",
                         horizontalalignment='center', verticalalignment='center',
                         transform=self.ax.transAxes, fontdict={'size': 12, 'color': 'grey'})
            if hasattr(self,
                       '_last_valid_xlim_for_redraw') and recalculate_layout_and_graph:  # Сброс только если полный пересчет
                del self._last_valid_xlim_for_redraw
                del self._last_valid_ylim_for_redraw
            self.canvas.draw_idle()
            return

        node_colors = []
        cycle_nodes_set = set(cycle_nodes_list) if cycle_nodes_list else set()


        node_list_for_drawing = list(self.graph_G.nodes())

        for node in node_list_for_drawing:
            if node in cycle_nodes_set:
                node_colors.append(self.node_color_cycle)
            else:
                node_colors.append(self.node_color_default)

        # Используем self.node_size_val
        nx.draw_networkx_nodes(self.graph_G, self.graph_pos, ax=self.ax, nodelist=node_list_for_drawing,
                               node_color=node_colors, node_size=self.node_size_val,
                               alpha=0.95, edgecolors='black', linewidths=0.5)
        nx.draw_networkx_labels(self.graph_G, self.graph_pos, ax=self.ax, font_size=9,
                                font_weight="bold", font_color="black")

        cycle_edge_set = set()
        if cycle_nodes_list:
            for i in range(len(cycle_nodes_list)):
                u_cycle = cycle_nodes_list[i]
                v_cycle = cycle_nodes_list[(i + 1) % len(cycle_nodes_list)]
                if self.graph_G.has_edge(u_cycle, v_cycle):  # Убедимся, что ребро существует в графе
                    cycle_edge_set.add((u_cycle, v_cycle))

        normal_edges = []
        cycle_edges_to_draw = []
        for u, v in self.graph_G.edges():
            if (u, v) in cycle_edge_set:
                cycle_edges_to_draw.append((u, v))
            else:
                normal_edges.append((u, v))

        connection_style_with_rad = 'arc3,rad=0.15'

        nx.draw_networkx_edges(self.graph_G, self.graph_pos, ax=self.ax, edgelist=normal_edges,
                               edge_color=self.edge_color_default,
                               width=1.5, arrowsize=20,
                               node_size=self.node_size_val,
                               connectionstyle=connection_style_with_rad)

        if cycle_edges_to_draw:
            nx.draw_networkx_edges(self.graph_G, self.graph_pos, ax=self.ax, edgelist=cycle_edges_to_draw,
                                   edge_color=self.edge_color_cycle,
                                   width=2.5, arrowsize=25, style='dashed',
                                   node_size=self.node_size_val,
                                   connectionstyle=connection_style_with_rad)

        if current_xlim and current_ylim:
            self.ax.set_xlim(current_xlim)
            self.ax.set_ylim(current_ylim)
            # Сохраняем эти пределы для следующего НЕ полного пересчета
            self._last_valid_xlim_for_redraw = current_xlim
            self._last_valid_ylim_for_redraw = current_ylim
        else:  # Либо полный пересчет, либо первый раз
            self.ax.autoscale_view()
            self._last_valid_xlim_for_redraw = self.ax.get_xlim()
            self._last_valid_ylim_for_redraw = self.ax.get_ylim()

        self.fig.tight_layout(pad=1.0)
        self.canvas.draw_idle()

    def run_detection_and_draw(self):
        input_text = self.input_area.get("1.0", tk.END)
        parsed_graph = self.parse_input(input_text)

        if parsed_graph is None:
            self.display_result("Ошибка в формате ввода. Проверьте сообщения.", self.error_color_fg)
            if VISUALIZATION_ENABLED:
                self.parsed_graph_for_draw = None  # Очищаем сохраненный граф
                self.cycle_nodes_for_draw = None
                self.draw_graph_visual(None, None, recalculate_layout_and_graph=True)
            return

        self.parsed_graph_for_draw = parsed_graph  # Сохраняем для перетаскивания

        all_graph_nodes_parsed = set()
        if parsed_graph:
            all_graph_nodes_parsed.update(parsed_graph.keys())
            for deps in parsed_graph.values():
                all_graph_nodes_parsed.update(deps)

        if not all_graph_nodes_parsed and not parsed_graph:  # Проверяем, если граф действительно пуст
            self.display_result("Граф пуст (нет узлов для анализа). Тупиков нет.", self.info_color_fg)
            if VISUALIZATION_ENABLED:
                self.cycle_nodes_for_draw = None
                self.draw_graph_visual(self.parsed_graph_for_draw, None, recalculate_layout_and_graph=True)
            return

        cycle = detect_deadlock_wfg(parsed_graph)
        self.cycle_nodes_for_draw = cycle  # Сохраняем для перетаскивания

        # Сбрасываем сохраненные пределы перед полным пересчетом layout'а, чтобы autoscale сработал корректно
        if hasattr(self, '_last_valid_xlim_for_redraw'):
            del self._last_valid_xlim_for_redraw
            del self._last_valid_ylim_for_redraw

        if cycle:
            cycle_str = " -> ".join(cycle) + " -> " + cycle[0]
            result_text = f"ОБНАРУЖЕН ТУПИК!\nЦикл: {cycle_str}"
            self.display_result(result_text, self.error_color_fg)
            if VISUALIZATION_ENABLED:
                self.draw_graph_visual(self.parsed_graph_for_draw, self.cycle_nodes_for_draw,
                                       recalculate_layout_and_graph=True)
        else:
            result_text = "Тупиков не обнаружено."
            self.display_result(result_text, self.success_color_fg)
            if VISUALIZATION_ENABLED:
                self.draw_graph_visual(self.parsed_graph_for_draw, None, recalculate_layout_and_graph=True)

    def clear_all(self):
        self.input_area.delete("1.0", tk.END)
        self.input_area.insert(tk.END,
                               "# Пример с тупиком:\nP1 -> P2\nP2 -> P3\nP3 -> P1\nP4 -> P1\n\n# Пример без тупика:\nA -> B\nB -> C\nX -> Y")
        self.display_result("", self.info_color_fg)

        self.parsed_graph_for_draw = None
        self.cycle_nodes_for_draw = None
        self.graph_G = None  # Сбрасываем объект графа
        self.graph_pos = None  # Сбрасываем позиции
        self.dragged_node_id = None  # Сбрасываем перетаскиваемую вершину

        if VISUALIZATION_ENABLED:
            if hasattr(self, '_last_valid_xlim_for_redraw'):  # Сбрасываем сохраненные пределы
                del self._last_valid_xlim_for_redraw
                del self._last_valid_ylim_for_redraw
            self.draw_graph_visual(None, None, recalculate_layout_and_graph=True)
        self.input_area.focus_set()


if __name__ == "__main__":  # pragma: no cover
    root = tk.Tk()
    app = DeadlockApp(root)
    root.mainloop()