function parseTimeoutExpress(timeout_express) {
    const match = timeout_express.match(/(\d+)([mhd])/);
    if (!match) return null;

    const [_, value, unit] = match;
    const unitInSeconds = {
        'm': 60,
        'h': 3600,
        'd': 86400
    };

    return parseInt(value) * unitInSeconds[unit];
}

function formatTime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainingSeconds = seconds % 60;

    let timeString = '';
    if (hours > 0) timeString += `${hours}小时`;
    if (minutes > 0) timeString += `${minutes}分钟`;
    if (remainingSeconds > 0 || timeString === '') timeString += `${remainingSeconds}秒`;

    return timeString;
}

class PaymentTimer {
    constructor(createTime, timeoutExpress, onTick, onTimeout) {
        this.createTime = new Date(createTime);
        this.timeoutSeconds = parseTimeoutExpress(timeoutExpress);
        this.onTick = onTick;
        this.onTimeout = onTimeout;
        this.timer = null;
    }

    start() {
        this.stop();
        this.timer = setInterval(() => {
            const now = new Date();
            const elapsedSeconds = Math.floor((now - this.createTime) / 1000);
            const remainingSeconds = this.timeoutSeconds - elapsedSeconds;

            if (remainingSeconds <= 0) {
                this.stop();
                this.onTimeout();
            } else {
                this.onTick(formatTime(remainingSeconds));
            }
        }, 1000);
    }

    stop() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
    }
}
