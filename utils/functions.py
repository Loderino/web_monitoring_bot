def format_duration(seconds: int, full_words: bool = False) -> str:
    """
    Formats the duration into a readable format

    Args:
        seconds (int): Number of seconds.
        full_words (bool): if True, then the timestamp designations will be full words. 
            Otherwise, by abbreviations. Defaults to False.

    Returns:
        str: Human-readable time format.
    """
    def format_full_words(num, word):
        match word:
            case "s":
                if num%10 == 1:
                    return "секунда"
                if num%10 in range(2, 5):
                    return "секунды"
                return "секунд"
            case "m":
                if num%10 == 1:
                    return "минута"
                if num%10 in range(2, 5):
                    return "минуты"
                return "минут"
            case "h":
                if num%10 == 1:
                    return "час"
                if num%10 in range(2, 5):
                    return "часа"
                return "часов"
            case "d":
                if num%10 == 1:
                    return "день"
                if num%10 in range(2, 5):
                    return "дня"
                return "дней"
        
    if seconds < 60:
        if full_words:
            return f"{seconds} {format_full_words(seconds, 's')}"
        return f"{seconds}с"
    if seconds < 3600:
        if full_words:
            if seconds%60 == 0:
                return f"{seconds // 60} {format_full_words(seconds // 60, 'm')}"
            return f"{seconds // 60} {format_full_words(seconds // 60, 'm')} {seconds % 60} {format_full_words(seconds, 's')}"
        return f"{seconds // 60}м {seconds % 60}с"
    if seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if full_words:
            if minutes == 0:
                return f"{hours} {format_full_words(hours, 'h')}"
            return f"{hours} {format_full_words(hours, 'h')} {minutes} {format_full_words(minutes, 'm')}"
        return f"{hours}ч {minutes}м"
    days = seconds // 86400
    hours = seconds % 86400
    if full_words:
        if hours == 0:
            return f"{days} {format_full_words(days, 'd')}"
        return f"{days} {format_full_words(days, 'd')} {hours} {format_full_words(hours, 'h')}"    
    return f"{days}д {hours}ч"